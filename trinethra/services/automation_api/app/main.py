from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras
import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


app = FastAPI(title="Trinetra - Automation API", version="0.5.0")


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
    "https://trinethra-model-service.onrender.com",
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

APPROVE_CUTOFF = DEFAULT_POLICY.get(CAUTION_MODE, DEFAULT_POLICY["GREEN"])["approve_cutoff"]
BLOCK_CUTOFF = DEFAULT_POLICY.get(CAUTION_MODE, DEFAULT_POLICY["GREEN"])["block_cutoff"]


# ----------------------------
# Request schema
# Supports BOTH:
# 1) legacy API shape: {domain, event_type, entity_id, payload}
# 2) UI shape: {amount, zip, incident_date, ...}
# ----------------------------
class ProcessClaimRequest(BaseModel):
    # legacy shape
    domain: Optional[str] = None
    event_type: Optional[str] = None
    entity_id: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None

    # UI shape
    amount: Optional[float] = None
    zip: Optional[str] = None
    incident_date: Optional[str] = None
    days_since_policy_start: Optional[int] = None
    age: Optional[int] = None
    years_with_insurer: Optional[int] = None
    previous_claims: Optional[int] = None
    channel: Optional[str] = None
    police_report_filed: Optional[bool] = None
    injury_involved: Optional[bool] = None

    # allow extra fields safely
    model_config = {"extra": "allow"}


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


def _table_columns(table_name: str) -> set[str]:
    sql = """
    SELECT column_name
    FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = %s
    """
    with _db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (table_name,))
            rows = cur.fetchall()
    return {row["column_name"] for row in rows}


def _insert_event(domain: str, event_type: str, entity_id: str, payload: Dict[str, Any]) -> str:
    sql = """
    INSERT INTO events (domain, event_type, entity_id, payload)
    VALUES (%s, %s, %s, %s::jsonb)
    RETURNING event_id::text;
    """
    try:
        with _db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (domain, event_type, entity_id, psycopg2.extras.Json(payload)),
                )
                row = cur.fetchone()
                return str(row["event_id"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB insert event failed: {e}")


def _insert_decision(
    event_id: str,
    action: str,
    confidence: float,
    reason_codes: List[str],
    caution_mode: str,
    risk_signal: float,
    threshold: float,
    model_version: str,
) -> None:
    cols = _table_columns("decision_events")

    values: Dict[str, Any] = {}

    if "event_id" in cols:
        values["event_id"] = event_id
    if "action" in cols:
        values["action"] = action
    if "confidence" in cols:
        values["confidence"] = confidence
    if "reason_codes" in cols:
        values["reason_codes"] = reason_codes
    if "rule_hits" in cols:
        values["rule_hits"] = []
    if "caution_mode" in cols:
        values["caution_mode"] = caution_mode
    if "risk_signal" in cols:
        values["risk_signal"] = risk_signal
    if "threshold" in cols:
        values["threshold"] = threshold
    if "model_version" in cols:
        values["model_version"] = model_version

    if not values:
        raise HTTPException(status_code=500, detail="decision_events has no compatible columns")

    columns_sql = ", ".join(values.keys())
    placeholders_sql = ", ".join(["%s"] * len(values))
    params = list(values.values())

    sql = f"INSERT INTO decision_events ({columns_sql}) VALUES ({placeholders_sql})"

    try:
        with _db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB insert decision failed: {e}")


# ----------------------------
# Model call
# ----------------------------
def _call_model(payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{MODEL_URL}/predict"
    start = time.time()

    try:
        response = requests.post(url, json={"payload": payload}, timeout=15)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"model-service call failed: {e}")

    latency_ms = int((time.time() - start) * 1000)

    if response.status_code != 200:
        raise HTTPException(status_code=502, detail=response.text)

    try:
        data = response.json()
    except Exception:
        raise HTTPException(status_code=502, detail="model-service returned non-JSON response")

    try:
        risk_signal = float(data["risk_signal"])
        threshold = float(data["threshold"])
        model_version = str(data["model_version"])
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"model-service returned invalid payload: {e}")

    return {
        "risk_signal": risk_signal,
        "threshold": threshold,
        "model_version": model_version,
        "latency_ms": latency_ms,
    }


# ----------------------------
# Decision logic
# ----------------------------
def _decide(risk: float) -> tuple[str, float, List[str]]:
    if risk >= BLOCK_CUTOFF:
        return "BLOCK", 0.95, ["MODEL_RISK_BLOCK_CUTOFF"]

    if risk < APPROVE_CUTOFF:
        return "AUTO_APPROVE", 0.85, ["MODEL_RISK_BELOW_APPROVE_CUTOFF"]

    return "ROUTE_TO_REVIEW", 0.90, ["MODEL_RISK_IN_REVIEW_BAND"]


def _build_payload(req: ProcessClaimRequest) -> tuple[str, str, str, Dict[str, Any]]:
    data = req.model_dump(exclude_none=True)

    # Legacy API format
    if req.payload is not None:
        domain = req.domain or "insurance"
        event_type = req.event_type or "claim"
        entity_id = req.entity_id or f"claim_{int(time.time())}"
        return domain, event_type, entity_id, req.payload

    # UI format
    payload = {
        k: v
        for k, v in data.items()
        if k not in {"domain", "event_type", "entity_id", "payload"}
    }

    if not payload:
        raise HTTPException(status_code=400, detail="No claim payload provided")

    domain = req.domain or "insurance"
    event_type = req.event_type or "claim"
    entity_id = req.entity_id or f"claim_{int(time.time())}"

    return domain, event_type, entity_id, payload


# ----------------------------
# Health
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
@app.post("/process_claim")
def process_claim(req: ProcessClaimRequest):
    domain, event_type, entity_id, payload = _build_payload(req)

    event_id = _insert_event(domain, event_type, entity_id, payload)

    model = _call_model(payload)

    risk = model["risk_signal"]
    threshold = model["threshold"]
    version = model["model_version"]
    latency = model["latency_ms"]

    action, confidence, reason_codes = _decide(risk)

    _insert_decision(
        event_id=event_id,
        action=action,
        confidence=confidence,
        reason_codes=reason_codes,
        caution_mode=CAUTION_MODE,
        risk_signal=risk,
        threshold=threshold,
        model_version=version,
    )

    llm_summary = (
        f"Claim evaluated with risk score {risk:.2f}. "
        f"Decision {action} applied under {CAUTION_MODE} policy mode."
    )

    # Return BOTH top-level and nested summary for UI compatibility
    return {
        "action": action,
        "confidence": confidence,
        "reason_codes": reason_codes,
        "rule_hits": {},
        "caution_mode": CAUTION_MODE,
        "risk_signal": risk,
        "threshold": threshold,
        "model_version": version,
        "latency_ms": latency,
        "policy_version": POLICY_VERSION,
        "business_impact": {},
        "observability": {
            "llm_summary": llm_summary,
        },
        "llm_summary": llm_summary,
        "entity_id": entity_id,
        "event_id": event_id,
    }


# ----------------------------
# Decisions
# ----------------------------
@app.get("/decisions")
def get_decisions(limit: int = Query(50, ge=1, le=200)):
    cols = _table_columns("decision_events")

    if "decision_id" in cols:
        id_expr = "decision_id::text AS decision_id"
    elif "decision" in cols:
        id_expr = "decision::text AS decision_id"
    else:
        id_expr = "NULL::text AS decision_id"

    action_expr = "action" if "action" in cols else "NULL::text AS action"
    confidence_expr = "confidence" if "confidence" in cols else "NULL::float AS confidence"
    mode_expr = "caution_mode" if "caution_mode" in cols else "NULL::text AS caution_mode"
    risk_expr = "risk_signal" if "risk_signal" in cols else "NULL::float AS risk_signal"
    model_expr = "model_version" if "model_version" in cols else "NULL::text AS model_version"

    if "timestamp" in cols:
        order_expr = "timestamp DESC"
    elif "created_at" in cols:
        order_expr = "created_at DESC"
    else:
        order_expr = "1"

    sql = f"""
    SELECT
        {id_expr},
        {action_expr},
        {confidence_expr},
        {mode_expr},
        {risk_expr},
        {model_expr}
    FROM decision_events
    ORDER BY {order_expr}
    LIMIT %s
    """

    try:
        with _db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (limit,))
                rows = cur.fetchall()

        # add common aliases for frontend safety
        for row in rows:
            row["mode"] = row.get("caution_mode")
            row["id"] = row.get("decision_id")

        return rows

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB read failed: {e}")


# ----------------------------
# KPIs
# ----------------------------
@app.get("/kpis")
def get_kpis():
    sql = """
    SELECT
        COUNT(*)::int AS total,
        COALESCE(SUM(CASE WHEN action = 'AUTO_APPROVE' THEN 1 ELSE 0 END), 0)::int AS approvals,
        COALESCE(SUM(CASE WHEN action = 'BLOCK' THEN 1 ELSE 0 END), 0)::int AS blocks
    FROM decision_events
    """

    try:
        with _db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                row = cur.fetchone()

        total = int(row["total"] or 0)
        approvals = int(row["approvals"] or 0)
        blocks = int(row["blocks"] or 0)
        fraud_rate = (blocks / total) if total else 0.0

        # return multiple key styles for UI compatibility
        return {
            "total": total,
            "total_decisions": total,
            "approvals": approvals,
            "blocks": blocks,
            "fraud_rate": fraud_rate,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"KPI query failed: {e}")