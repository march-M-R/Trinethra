from __future__ import annotations

import os
import time
from typing import Any, Dict, List

import psycopg2
import psycopg2.extras
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


app = FastAPI(title="Trinetra - Automation API", version="0.3.0")

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
# Config
# ----------------------------
CAUTION_MODE = os.getenv("CAUTION_MODE", "GREEN").upper()
POLICY_VERSION = os.getenv("POLICY_VERSION", "policy_v2")

MODEL_URL = os.getenv(
    "MODEL_URL",
    "https://trinethra-model-service.onrender.com"
)

DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")


# ----------------------------
# Policy thresholds
# ----------------------------
DEFAULT_POLICY = {
    "GREEN": {"approve_cutoff": 0.70, "block_cutoff": 0.92},
    "YELLOW": {"approve_cutoff": 0.65, "block_cutoff": 0.88},
    "RED": {"approve_cutoff": 0.60, "block_cutoff": 0.85},
}

APPROVE_CUTOFF = DEFAULT_POLICY[CAUTION_MODE]["approve_cutoff"]
BLOCK_CUTOFF = DEFAULT_POLICY[CAUTION_MODE]["block_cutoff"]


# ----------------------------
# Schemas
# ----------------------------
class ProcessClaimRequest(BaseModel):
    domain: str
    event_type: str
    entity_id: str
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
    business_impact: Dict[str, Any]
    observability: Dict[str, Any]


# ----------------------------
# Database connection
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


# ----------------------------
# Insert event
# ----------------------------
def _insert_event(domain, event_type, entity_id, payload):

    sql = """
    INSERT INTO events (domain, event_type, entity_id, payload)
    VALUES (%s,%s,%s,%s::jsonb)
    RETURNING event_id::text;
    """

    with _db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (domain, event_type, entity_id, psycopg2.extras.Json(payload)),
            )
            return cur.fetchone()["event_id"]


# ----------------------------
# Insert decision
# ----------------------------
def _insert_decision(
    event_id,
    action,
    confidence,
    reason_codes,
    caution_mode,
    risk_signal,
    threshold,
    model_version,
):

    sql = """
    INSERT INTO decision_events
    (event_id,action,confidence,reason_codes,caution_mode,risk_signal,threshold,model_version)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """

    with _db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    event_id,
                    action,
                    confidence,
                    reason_codes,
                    caution_mode,
                    risk_signal,
                    threshold,
                    model_version,
                ),
            )


# ----------------------------
# Call model service
# ----------------------------
def _call_model(payload: Dict[str, Any]):

    url = f"{MODEL_URL}/predict"

    start = time.time()

    try:
        r = requests.post(url, json={"payload": payload}, timeout=10)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"model-service call failed: {e}")

    latency = int((time.time() - start) * 1000)

    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=r.text)

    data = r.json()

    return {
        "risk_signal": float(data["risk_signal"]),
        "threshold": float(data["threshold"]),
        "model_version": data["model_version"],
        "latency_ms": latency,
    }


# ----------------------------
# Decision logic
# ----------------------------
def _decide(risk: float):

    if risk >= BLOCK_CUTOFF:
        return "BLOCK", 0.95, ["MODEL_RISK_BLOCK_CUTOFF"]

    if risk < APPROVE_CUTOFF:
        return "AUTO_APPROVE", 0.85, ["MODEL_RISK_BELOW_APPROVE_CUTOFF"]

    return "ROUTE_TO_REVIEW", 0.9, ["MODEL_RISK_IN_REVIEW_BAND"]


# ----------------------------
# Health endpoint
# ----------------------------
@app.get("/health")
def health():

    return {
        "status": "ok",
        "service": "automation_api",
        "mode": CAUTION_MODE,
        "policy_version": POLICY_VERSION,
    }


# ----------------------------
# Process Claim
# ----------------------------
@app.post("/process_claim", response_model=ProcessClaimResponse)
def process_claim(req: ProcessClaimRequest):

    event_id = _insert_event(req.domain, req.event_type, req.entity_id, req.payload)

    model = _call_model(req.payload)

    risk = model["risk_signal"]
    threshold = model["threshold"]
    version = model["model_version"]
    latency = model["latency_ms"]

    action, confidence, reason_codes = _decide(risk)

    _insert_decision(
        event_id,
        action,
        confidence,
        reason_codes,
        CAUTION_MODE,
        risk,
        threshold,
        version,
    )

    return ProcessClaimResponse(
        action=action,
        confidence=confidence,
        reason_codes=reason_codes,
        rule_hits={},
        caution_mode=CAUTION_MODE,
        risk_signal=risk,
        threshold=threshold,
        model_version=version,
        latency_ms=latency,
        policy_version=POLICY_VERSION,
        business_impact={},
        observability={
            "llm_summary": f"Claim evaluated with risk score {risk:.2f}. Decision {action} applied."
        },
    )


# ----------------------------
# Decisions endpoint
# ----------------------------
@app.get("/decisions")
def get_decisions(limit: int = 50):

    sql = """
    SELECT
        decision_id,
        action,
        confidence,
        caution_mode,
        risk_signal,
        model_version
    FROM decision_events
    ORDER BY timestamp DESC
    LIMIT %s
    """

    with _db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (limit,))
            rows = cur.fetchall()

    return rows


# ----------------------------
# KPI endpoint
# ----------------------------
@app.get("/kpis")
def get_kpis():

    sql = """
    SELECT
        COUNT(*) as total,
        SUM(CASE WHEN action='AUTO_APPROVE' THEN 1 ELSE 0 END) as approvals,
        SUM(CASE WHEN action='BLOCK' THEN 1 ELSE 0 END) as blocks
    FROM decision_events
    """

    with _db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone()

    total = row["total"] or 0
    approvals = row["approvals"] or 0
    blocks = row["blocks"] or 0

    fraud_rate = (blocks / total) if total else 0

    return {
        "total_decisions": total,
        "approvals": approvals,
        "blocks": blocks,
        "fraud_rate": fraud_rate
    }