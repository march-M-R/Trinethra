from __future__ import annotations

import os
import time
import math
from datetime import date
from uuid import UUID
from contextlib import contextmanager
from typing import Any, Dict, List

import psycopg2
import psycopg2.extras
import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


app = FastAPI(title="Trinetra Automation API", version="1.1")


# ----------------------------
# CORS
# ----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----------------------------
# ENV
# ----------------------------
MODEL_URL = os.getenv(
    "MODEL_URL",
    "https://trinethra-model-service.onrender.com",
)

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "trinethra")
DB_USER = os.getenv("DB_USER", "trinethra_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "trinethra_pass")


# ----------------------------
# Policy
# ----------------------------
# Blocking requires a separately validated, explicitly configured policy.
BLOCK_CUTOFF = float(os.environ["BLOCK_CUTOFF"]) if os.getenv("BLOCK_CUTOFF") else None
if BLOCK_CUTOFF is not None and not 0 < BLOCK_CUTOFF <= 1:
    raise ValueError("BLOCK_CUTOFF must be in (0, 1]")


# ----------------------------
# Request schema (matches UI)
# ----------------------------
class ProcessClaimRequest(BaseModel):
    claim_id: str = Field(min_length=1, max_length=128)
    policy_id: str = Field(min_length=1, max_length=128)
    claim_type: str

    amount: float = Field(gt=0, allow_inf_nan=False)
    zip: str
    incident_date: date
    days_since_policy_start: int = Field(ge=0)

    age: int = Field(ge=16, le=120)
    years_with_insurer: int = Field(ge=0)
    previous_claims: int = Field(ge=0)

    channel: str
    police_report_filed: bool = False
    injury_involved: bool = False


# ----------------------------
# DB connection
# ----------------------------
@contextmanager
def db():
    database_url = os.getenv("DATABASE_URL")
    connection_options = {} if database_url else {
        "host": DB_HOST, "port": DB_PORT, "dbname": DB_NAME,
        "user": DB_USER, "password": DB_PASSWORD,
    }
    conn = psycopg2.connect(
        database_url or "", connect_timeout=5,
        cursor_factory=psycopg2.extras.RealDictCursor,
        **connection_options,
    )

    try:
        with conn:
            yield conn
    finally:
        conn.close()


# ----------------------------
# Health
# ----------------------------
@app.get("/health")
def health():
    try:
        with db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM decision_events LIMIT 1")
        return {"status": "ok", "database": "ok"}
    except Exception:
        return JSONResponse(status_code=503, content={"status": "degraded", "database": "unavailable"})


# ----------------------------
# Model call
# ----------------------------
def call_model(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        r = requests.post(
            f"{MODEL_URL}/predict",
            json={"payload": payload},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()

        risk, threshold = float(data["risk_signal"]), float(data["threshold"])
        if not math.isfinite(risk) or not 0 <= risk <= 1:
            raise ValueError("Invalid model risk score")
        if not math.isfinite(threshold) or not 0 < threshold <= 1:
            raise ValueError("Invalid model threshold")
        if not isinstance(data.get("degraded"), bool):
            raise ValueError("Model response must include degraded status")
        if BLOCK_CUTOFF is not None and BLOCK_CUTOFF <= threshold:
            raise ValueError("BLOCK_CUTOFF must exceed the model review threshold")
        return {
            "risk_signal": risk, "threshold": threshold,
            "model_version": str(data["model_version"]),
            "degraded": data["degraded"], "warning": data.get("warning"),
        }

    except Exception as e:
        raise HTTPException(status_code=502, detail=f"model-service call failed: {e}")


# ----------------------------
# Decision logic
# ----------------------------
def decide(risk: float, threshold: float, degraded: bool = False) -> tuple[str, List[str]]:
    if degraded:
        return "ROUTE_TO_REVIEW", ["MODEL_DEGRADED_MANUAL_REVIEW"]
    if BLOCK_CUTOFF is not None and risk >= BLOCK_CUTOFF:
        return "BLOCK", ["MODEL_RISK_BLOCK_CUTOFF"]
    if risk < threshold:
        return "AUTO_APPROVE", ["MODEL_RISK_BELOW_REVIEW_THRESHOLD"]
    return "ROUTE_TO_REVIEW", ["MODEL_RISK_AT_OR_ABOVE_REVIEW_THRESHOLD"]


# ----------------------------
# Process Claim
# ----------------------------
@app.post("/process_claim")
def process_claim(req: ProcessClaimRequest):
    payload = req.model_dump(mode="json")
    if req.incident_date > date.today():
        raise HTTPException(status_code=422, detail="Incident date cannot be in the future")

    model_start = time.time()
    model = call_model(payload)
    latency_ms = int((time.time() - model_start) * 1000)

    risk = model["risk_signal"]
    threshold = model["threshold"]
    model_version = model["model_version"]

    action, reason_codes = decide(risk, threshold, model["degraded"])
    caution_mode = "AMBER" if model["degraded"] else "GREEN"
    latency_ms = int((time.time() - model_start) * 1000)
    summary = f"Risk score {risk:.3f}; review threshold {threshold:.3f}. Decision: {action}."
    observability = {
        "degraded": model["degraded"], "warning": model["warning"],
        "confidence_available": False,
        "input_limitations": "Partial intake mapped to vehicle-claims schema; missing attributes use defaults. Score is not a calibrated fraud probability.",
        "decision_summary": summary,
    }

    try:
        with db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO events(domain, event_type, entity_id, payload)
                    VALUES(%s, %s, %s, %s::jsonb)
                    RETURNING event_id
                    """,
                    (
                        "insurance",
                        "claim",
                        req.claim_id,
                        psycopg2.extras.Json(payload),
                    ),
                )

                event_id = cur.fetchone()["event_id"]

                cur.execute(
                    """
                    INSERT INTO decision_events
                    (event_id, action, confidence, reason_codes, caution_mode, risk_signal, threshold, model_version, policy_version, latency_ms, observability)
                    VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING decision_id
                    """,
                    (
                        event_id,
                        action,
                        0.0,  # Legacy NOT NULL column; unavailable, not a confidence estimate.
                        reason_codes,
                        caution_mode,
                        risk,
                        threshold,
                        model_version,
                        "policy_v3",
                        latency_ms,
                        psycopg2.extras.Json(observability),
                    ),
                )

                decision_id = str(cur.fetchone()["decision_id"])

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"database write failed: {e}")


    return {
        "action": action,
        "decision_id": decision_id,
        "event_id": str(event_id),
        "confidence": None,
        "degraded": model["degraded"],
        "warning": model["warning"],
        "reason_codes": reason_codes,
        "rule_hits": [],
        "caution_mode": caution_mode,
        "risk_signal": risk,
        "threshold": threshold,
        "model_version": model_version,
        "latency_ms": latency_ms,
        "policy_version": "policy_v3",
        "business_impact": {},
        "observability": observability,
        "decision_summary": summary
    }


# ----------------------------
# Decisions
# ----------------------------
@app.get("/decisions")
def decisions(limit: int = Query(50, ge=1, le=200)):
    try:
        with db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        d.decision_id::text AS decision_id,
                        d.event_id::text AS event_id,
                        e.entity_id AS claim_id,
                        d.action,
                        d.confidence,
                        d.reason_codes,
                        d.rule_hits,
                        d.risk_signal,
                        d.threshold,
                        d.caution_mode,
                        d.model_version,
                        d.policy_version,
                        d.latency_ms,
                        d.business_impact,
                        d.observability,
                        d.timestamp
                    FROM decision_events d
                    JOIN events e ON e.event_id = d.event_id
                    ORDER BY d.timestamp DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = cur.fetchall()

        for row in rows:
            row["mode"] = row.get("caution_mode")
            row["confidence"] = None

        return rows

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB read failed: {e}")


@app.get("/decisions/{decision_id}")
def decision_detail(decision_id: UUID):
    try:
        with db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        d.decision_id::text AS decision_id,
                        d.event_id::text AS event_id,
                        e.entity_id AS claim_id,
                        e.payload,
                        d.action,
                        d.confidence,
                        d.reason_codes,
                        d.rule_hits,
                        d.caution_mode,
                        d.risk_signal,
                        d.threshold,
                        d.model_version,
                        d.policy_version,
                        d.latency_ms,
                        d.business_impact,
                        d.observability,
                        d.timestamp
                    FROM decision_events d
                    JOIN events e ON e.event_id = d.event_id
                    WHERE d.decision_id = %s
                    """,
                    (str(decision_id),),
                )
                row = cur.fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="Decision not found")
        row["mode"] = row.get("caution_mode")
        row["confidence"] = None
        return row
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB read failed: {e}")


# ----------------------------
# KPIs
# ----------------------------
@app.get("/kpis")
def kpis(window_hours: int = Query(24, ge=1, le=720)):
    try:
        with db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        COUNT(*) AS total,
                        COALESCE(SUM(CASE WHEN action = 'AUTO_APPROVE' THEN 1 ELSE 0 END), 0) AS approvals,
                        COALESCE(SUM(CASE WHEN action = 'BLOCK' THEN 1 ELSE 0 END), 0) AS blocks,
                        COALESCE(SUM(CASE WHEN action = 'ROUTE_TO_REVIEW' THEN 1 ELSE 0 END), 0) AS reviews
                    FROM decision_events
                    WHERE timestamp >= NOW() - (%s * INTERVAL '1 hour')
                    """,
                    (window_hours,),
                )

                row = cur.fetchone()

        total = int(row["total"] or 0)
        approvals = int(row["approvals"] or 0)
        blocks = int(row["blocks"] or 0)
        reviews = int(row["reviews"] or 0)
        block_rate = blocks / total if total else 0.0

        return {
            "total": total,
            "total_decisions": total,
            "approvals": approvals,
            "blocks": blocks,
            "reviews": reviews,
            "block_rate": block_rate,
            "window_hours": window_hours,
            "by_action": {
                "AUTO_APPROVE": approvals,
                "ROUTE_TO_REVIEW": reviews,
                "BLOCK": blocks,
            },
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"KPI query failed: {e}")
