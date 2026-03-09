from __future__ import annotations

import os
import time
from typing import Any, Dict, List

import psycopg2
import psycopg2.extras
import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


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

DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")


# ----------------------------
# Policy
# ----------------------------
APPROVE_CUTOFF = 0.70
BLOCK_CUTOFF = 0.92


# ----------------------------
# Request schema (matches UI)
# ----------------------------
class ProcessClaimRequest(BaseModel):
    claim_id: str
    policy_id: str
    claim_type: str

    amount: float
    zip: str
    incident_date: str
    days_since_policy_start: int

    age: int
    years_with_insurer: int
    previous_claims: int

    channel: str
    police_report_filed: bool = False
    injury_involved: bool = False


# ----------------------------
# DB connection
# ----------------------------
def db():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


# ----------------------------
# Health
# ----------------------------
@app.get("/health")
def health():
    return {"status": "ok"}


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

        return {
            "risk_signal": float(data["risk_signal"]),
            "threshold": float(data["threshold"]),
            "model_version": str(data["model_version"]),
        }

    except Exception as e:
        raise HTTPException(status_code=502, detail=f"model-service call failed: {e}")


# ----------------------------
# Decision logic
# ----------------------------
def decide(risk: float) -> tuple[str, float, List[str]]:
    if risk >= BLOCK_CUTOFF:
        return "BLOCK", 0.95, ["MODEL_RISK_BLOCK_CUTOFF"]

    if risk < APPROVE_CUTOFF:
        return "AUTO_APPROVE", 0.85, ["MODEL_RISK_BELOW_APPROVE_CUTOFF"]

    return "ROUTE_TO_REVIEW", 0.90, ["MODEL_RISK_IN_REVIEW_BAND"]


# ----------------------------
# Process Claim
# ----------------------------
@app.post("/process_claim")
def process_claim(req: ProcessClaimRequest):
    payload = req.model_dump()

    model_start = time.time()
    model = call_model(payload)
    latency_ms = int((time.time() - model_start) * 1000)

    risk = model["risk_signal"]
    threshold = model["threshold"]
    model_version = model["model_version"]

    action, confidence, reason_codes = decide(risk)

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
                    (event_id, action, confidence, reason_codes, caution_mode, risk_signal, threshold, model_version)
                    VALUES(%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        event_id,
                        action,
                        confidence,
                        reason_codes,
                        "GREEN",
                        risk,
                        threshold,
                        model_version,
                    ),
                )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"database write failed: {e}")

    summary = f"Risk score {risk:.2f}. Decision: {action}"

    return {
        "action": action,
        "confidence": confidence,
        "reason_codes": reason_codes,
        "rule_hits": {},
        "caution_mode": "GREEN",
        "risk_signal": risk,
        "threshold": threshold,
        "model_version": model_version,
        "latency_ms": latency_ms,
        "policy_version": "policy_v2",
        "business_impact": {},
        "observability": {
            "llm_summary": summary
        },
        "llm_summary": summary
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
                        decision::text AS decision_id,
                        action,
                        confidence,
                        risk_signal,
                        caution_mode,
                        model_version
                    FROM decision_events
                    ORDER BY timestamp DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = cur.fetchall()

        for row in rows:
            row["mode"] = row.get("caution_mode")

        return rows

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB read failed: {e}")


# ----------------------------
# KPIs
# ----------------------------
@app.get("/kpis")
def kpis():
    try:
        with db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        COUNT(*) AS total,
                        COALESCE(SUM(CASE WHEN action = 'AUTO_APPROVE' THEN 1 ELSE 0 END), 0) AS approvals,
                        COALESCE(SUM(CASE WHEN action = 'BLOCK' THEN 1 ELSE 0 END), 0) AS blocks
                    FROM decision_events
                    """
                )

                row = cur.fetchone()

        total = int(row["total"] or 0)
        approvals = int(row["approvals"] or 0)
        blocks = int(row["blocks"] or 0)
        fraud_rate = blocks / total if total else 0.0

        return {
            "total": total,
            "total_decisions": total,
            "approvals": approvals,
            "blocks": blocks,
            "fraud_rate": fraud_rate,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"KPI query failed: {e}")