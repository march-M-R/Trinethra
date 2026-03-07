from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
import psycopg2.extras
import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


app = FastAPI(title="Trinetra - Automation API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------
# Config
# ----------------------------
CAUTION_MODE = os.getenv("CAUTION_MODE", "GREEN").upper()
POLICY_VERSION = os.getenv("POLICY_VERSION", "policy_v2")

MODEL_URL = os.getenv("MODEL_URL", "http://127.0.0.1:8002/predict")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "trinethra")
DB_USER = os.getenv("DB_USER", "trinethra_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "trinethra_pass")

# ----------------------------
# Policy cutoffs
# ----------------------------
DEFAULT_POLICY = {
    "GREEN": {"approve_cutoff": 0.70, "block_cutoff": 0.92},
    "YELLOW": {"approve_cutoff": 0.65, "block_cutoff": 0.88},
    "RED": {"approve_cutoff": 0.60, "block_cutoff": 0.85},
}

APPROVE_CUTOFF = float(
    os.getenv(
        "APPROVE_CUTOFF",
        DEFAULT_POLICY.get(CAUTION_MODE, DEFAULT_POLICY["GREEN"])["approve_cutoff"],
    )
)
BLOCK_CUTOFF = float(
    os.getenv(
        "BLOCK_CUTOFF",
        DEFAULT_POLICY.get(CAUTION_MODE, DEFAULT_POLICY["GREEN"])["block_cutoff"],
    )
)

# ----------------------------
# Schemas
# ----------------------------
class ProcessClaimRequest(BaseModel):
    domain: str = Field(..., examples=["claims"])
    event_type: str = Field(..., examples=["claim_submitted"])
    entity_id: str = Field(..., examples=["CLM-0001"])
    payload: Dict[str, Any] = Field(default_factory=dict)


class ProcessClaimResponse(BaseModel):
    action: str
    confidence: float
    reason_codes: List[str]
    rule_hits: Dict[str, Any]
    caution_mode: str

    risk_signal: float
    threshold: float
    model_version: str
    latency_ms: int

    policy_version: str
    business_impact: Dict[str, Any] = Field(default_factory=dict)
    observability: Dict[str, Any] = Field(default_factory=dict)

# ----------------------------
# DB helpers
# ----------------------------
def _db_conn():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


def _insert_event(domain: str, event_type: str, entity_id: str, payload: Dict[str, Any]) -> str:
    sql = """
    INSERT INTO events (domain, event_type, entity_id, payload)
    VALUES (%(domain)s, %(event_type)s, %(entity_id)s, %(payload)s::jsonb)
    RETURNING event_id::text;
    """
    with _db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                {
                    "domain": domain,
                    "event_type": event_type,
                    "entity_id": entity_id,
                    "payload": psycopg2.extras.Json(payload),
                },
            )
            row = cur.fetchone()
            return str(row["event_id"])


def _insert_decision(
    event_id: str,
    action: str,
    confidence: float,
    reason_codes: List[str],
    caution_mode: str,
    risk_signal: float,
    threshold: float,
    model_version: str,
    rule_hits: Optional[List[str]] = None,
) -> str:
    rule_hits = rule_hits or []

    sql = """
    INSERT INTO decision_events (
      event_id, action, confidence, reason_codes, rule_hits, caution_mode,
      risk_signal, threshold, model_version
    )
    VALUES (
      %(event_id)s::uuid, %(action)s, %(confidence)s,
      %(reason_codes)s::text[], %(rule_hits)s::text[], %(caution_mode)s,
      %(risk_signal)s, %(threshold)s, %(model_version)s
    )
    RETURNING decision_id::text;
    """
    with _db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                {
                    "event_id": event_id,
                    "action": action,
                    "confidence": confidence,
                    "reason_codes": reason_codes,
                    "rule_hits": rule_hits,
                    "caution_mode": caution_mode,
                    "risk_signal": risk_signal,
                    "threshold": threshold,
                    "model_version": model_version,
                },
            )
            row = cur.fetchone()
            return str(row["decision_id"])

# ----------------------------
# Model call
# ----------------------------
def _call_model(payload: Dict[str, Any]) -> Dict[str, Any]:
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="payload must be a JSON object")

    req_json = {"payload": payload}

    t0 = time.time()
    try:
        r = requests.post(MODEL_URL, json=req_json, timeout=10)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"model-service call failed: {e}")

    latency_ms = int((time.time() - t0) * 1000)

    if r.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"model-service call failed: {r.status_code} {r.text}",
        )

    data = r.json()
    for k in ("risk_signal", "threshold", "model_version"):
        if k not in data:
            raise HTTPException(status_code=502, detail=f"model-service returned missing key: {k}")

    data["latency_ms"] = int(data.get("latency_ms") or latency_ms)
    return data

# ----------------------------
# Decision policy
# ----------------------------
def _decide(risk: float) -> Tuple[str, float, List[str]]:
    if risk >= BLOCK_CUTOFF:
        return ("BLOCK", 0.95, ["MODEL_RISK_BLOCK_CUTOFF"])
    if risk < APPROVE_CUTOFF:
        return ("AUTO_APPROVE", 0.85, ["MODEL_RISK_BELOW_APPROVE_CUTOFF"])
    return ("ROUTE_TO_REVIEW", 0.90, ["MODEL_RISK_IN_REVIEW_BAND"])

# ----------------------------
# Endpoints
# ----------------------------
@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service": "automation_api",
        "mode": CAUTION_MODE,
        "policy_version": POLICY_VERSION,
    }


@app.get("/debug/build")
def debug_build() -> Dict[str, Any]:
    return {
        "file": __file__,
        "model_url": MODEL_URL,
        "caution_mode": CAUTION_MODE,
        "policy_version": POLICY_VERSION,
        "approve_cutoff": APPROVE_CUTOFF,
        "block_cutoff": BLOCK_CUTOFF,
    }


@app.get("/debug/policy")
def debug_policy() -> Dict[str, Any]:
    return {
        "active_mode": CAUTION_MODE,
        "active_cutoffs": {
            "approve_cutoff": APPROVE_CUTOFF,
            "block_cutoff": BLOCK_CUTOFF,
        },
        "defaults": DEFAULT_POLICY,
    }


@app.post("/process_claim", response_model=ProcessClaimResponse)
def process_claim(req: ProcessClaimRequest) -> ProcessClaimResponse:
    overall_t0 = time.time()

    try:
        event_id = _insert_event(req.domain, req.event_type, req.entity_id, req.payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB insert into events failed: {e}")

    model = _call_model(req.payload)
    risk = float(model["risk_signal"])
    thr = float(model["threshold"])
    ver = str(model["model_version"])
    model_latency = int(model.get("latency_ms") or 0)

    action, confidence, reason_codes = _decide(risk)

    try:
        _insert_decision(
            event_id=event_id,
            action=action,
            confidence=confidence,
            reason_codes=reason_codes,
            caution_mode=CAUTION_MODE,
            risk_signal=risk,
            threshold=thr,
            model_version=ver,
            rule_hits=[],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB insert into decision_events failed: {e}")

    overall_latency_ms = int((time.time() - overall_t0) * 1000)

    return ProcessClaimResponse(
        action=action,
        confidence=confidence,
        reason_codes=reason_codes,
        rule_hits={},
        caution_mode=CAUTION_MODE,
        risk_signal=risk,
        threshold=thr,
        model_version=ver,
        latency_ms=overall_latency_ms if overall_latency_ms > model_latency else model_latency,
        policy_version=POLICY_VERSION,
        business_impact={},
        observability={
            "model_endpoint": MODEL_URL,
            "event_id": event_id,
            "cutoffs": {
                "approve_cutoff": APPROVE_CUTOFF,
                "block_cutoff": BLOCK_CUTOFF,
            },
        },
    )


@app.get("/decisions")
def list_decisions(limit: int = Query(50, ge=1, le=200)):
    with _db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema='public' AND table_name='decision_events'
                  AND column_name IN ('timestamp','created_at','decision_time','event_time','inserted_at','ts')
                LIMIT 1;
                """
            )
            time_col = cur.fetchone()
            order_by = time_col["column_name"] if time_col else "decision_id"

            cur.execute(
                f"""
                SELECT
                  decision_id::text AS decision_id,
                  event_id::text AS event_id,
                  action,
                  confidence,
                  caution_mode,
                  risk_signal,
                  threshold,
                  model_version,
                  {order_by} AS sort_time
                FROM decision_events
                ORDER BY {order_by} DESC
                LIMIT %s;
                """,
                (limit,),
            )
            rows = cur.fetchall()

    return {"items": rows}


@app.get("/decisions/{decision_id}")
def get_decision(decision_id: str):
    with _db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM decision_events
                WHERE decision_id::text = %s
                   OR decision_id = %s::uuid
                """,
                (decision_id, decision_id),
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Decision not found")
    return row


@app.get("/kpis/summary")
def kpi_summary(window_hours: int = Query(24, ge=1, le=24 * 30)):
    with _db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema='public' AND table_name='decision_events'
                  AND column_name IN ('timestamp','created_at','decision_time','event_time','inserted_at','ts')
                LIMIT 1;
                """
            )
            d_time = cur.fetchone()

            if d_time:
                tcol = d_time["column_name"]
                cur.execute(
                    f"""
                    SELECT
                      COUNT(*)::int AS total_decisions,
                      COUNT(*) FILTER (WHERE action = 'AUTO_APPROVE')::int AS approvals,
                      COUNT(*) FILTER (WHERE action = 'BLOCK')::int AS blocks,
                      COUNT(*) FILTER (WHERE action = 'ROUTE_TO_REVIEW')::int AS reviews,
                      COALESCE(
                        ROUND(
                          100.0 * COUNT(*) FILTER (WHERE action = 'BLOCK') / NULLIF(COUNT(*), 0),
                          2
                        ),
                        0
                      ) AS fraud_rate
                    FROM decision_events
                    WHERE {tcol} >= NOW() - make_interval(hours => %s);
                    """,
                    (window_hours,),
                )
                return cur.fetchone()

            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema='public' AND table_name='events'
                  AND column_name IN ('created_at','event_time','inserted_at','ts')
                LIMIT 1;
                """
            )
            e_time = cur.fetchone()
            if not e_time:
                raise HTTPException(
                    status_code=500,
                    detail="No timestamp column found on decision_events or events. Add created_at TIMESTAMPTZ DEFAULT now().",
                )

            etcol = e_time["column_name"]
            cur.execute(
                f"""
                SELECT
                  COUNT(*)::int AS total_decisions,
                  COUNT(*) FILTER (WHERE d.action = 'AUTO_APPROVE')::int AS approvals,
                  COUNT(*) FILTER (WHERE d.action = 'BLOCK')::int AS blocks,
                  COUNT(*) FILTER (WHERE d.action = 'ROUTE_TO_REVIEW')::int AS reviews,
                  COALESCE(
                    ROUND(
                      100.0 * COUNT(*) FILTER (WHERE d.action = 'BLOCK') / NULLIF(COUNT(*), 0),
                      2
                    ),
                    0
                  ) AS fraud_rate
                FROM decision_events d
                JOIN events e ON e.event_id = d.event_id
                WHERE e.{etcol} >= NOW() - make_interval(hours => %s);
                """,
                (window_hours,),
            )
            return cur.fetchone()