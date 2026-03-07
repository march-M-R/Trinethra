from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from uuid import UUID, uuid4
from datetime import datetime, timezone
from typing import List, Any, Dict, Optional
import time
import os

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

import httpx

# ----------------------------
# Load env + create FastAPI app
# ----------------------------
load_dotenv()
app = FastAPI(title="Trinetra - Automation Layer")

# ----------------------------
# Constants / Defaults
# ----------------------------
POLICY_VERSION = "policy-1.0.0"

DOMAIN = "insurance_claims"
EVENT_TYPE = "claim_submitted"

# model service
MODEL_SERVICE_URL = os.getenv("MODEL_SERVICE_URL", "http://127.0.0.1:8001")
MODEL_TIMEOUT_SECS = float(os.getenv("MODEL_TIMEOUT_SECS", "3.0"))

# In demo, we allow runtime switching of mode via /mode.
# If not set, defaults to env CAUTION_MODE or GREEN.
CAUTION_MODE_RUNTIME: Optional[str] = None

# Cache model info (optional)
MODEL_VERSION_CACHE: Optional[str] = None
MODEL_THRESHOLD_CACHE: Optional[float] = None


# ----------------------------
# DB connection
# ----------------------------
def get_conn():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "trinetra"),
        user=os.getenv("DB_USER", "trinetra"),
        password=os.getenv("DB_PASSWORD", "trinetra"),
    )


# ----------------------------
# Pydantic models
# ----------------------------
class ClaimEvent(BaseModel):
    """
    This is the input event into the Automation Layer.
    NOTE: We DO NOT accept risk_signal from the user anymore.
    We will compute it by calling the Model Service.
    """
    event_id: UUID
    event_time: datetime
    entity_id: str  # customer / policyholder id in MVP

    # Core claim fields
    claim_amount: float = Field(gt=0)
    policy_limit: float = Field(gt=0)
    deductible: float = Field(ge=0)

    # Customer/policy context
    customer_tenure_days: int = Field(ge=0)
    customer_age_band: Optional[str] = "26_35"
    policy_age_days: int = Field(ge=0)

    # Prior history
    prior_claim_count_12m: int = Field(ge=0)
    prior_claim_amount_12m: float = Field(ge=0)
    prior_fraud_flag: int = Field(ge=0, le=1)

    # Claim context
    loss_type: Optional[str] = "AUTO_COLLISION"
    channel: Optional[str] = "MOBILE_APP"
    region: Optional[str] = "NJ"
    payment_method: Optional[str] = "ACH"

    # Reporting + documentation
    incident_reported_delay_days: int = Field(ge=0)
    has_police_report: int = Field(ge=0, le=1)
    document_count: int = Field(ge=0)

    # Risk telemetry
    device_risk_score: float = Field(ge=0.0, le=1.0)
    ip_risk_score: float = Field(ge=0.0, le=1.0)

    # Data quality / observability
    data_quality_score: float = Field(ge=0.0, le=1.0)
    missing_fields_count: int = Field(ge=0)
    inconsistent_fields_flag: int = Field(ge=0, le=1)

    # Submission metadata
    submission_hour: int = Field(ge=0, le=23)
    submission_day_of_week: int = Field(ge=0, le=6)


class ModeUpdate(BaseModel):
    mode: str  # GREEN / AMBER / RED


class DecisionOut(BaseModel):
    decision_id: str
    event_id: str
    timestamp: str
    entity_id: str
    action: str
    confidence: float
    reason_codes: List[str]
    policy_version: str
    model_version: str
    caution_mode: str
    rule_hits: List[str]
    outcome: str
    latency_ms: int
    business_impact: Dict[str, Any]
    # helpful extras
    risk_signal: float
    model_threshold: float


# ----------------------------
# Helpers: caution mode + business rules
# ----------------------------
def get_caution_mode() -> str:
    global CAUTION_MODE_RUNTIME
    if CAUTION_MODE_RUNTIME:
        return CAUTION_MODE_RUNTIME
    return os.getenv("CAUTION_MODE", "GREEN").upper()


def set_caution_mode(mode: str) -> str:
    mode = mode.upper().strip()
    if mode not in {"GREEN", "AMBER", "RED"}:
        raise ValueError("Mode must be one of GREEN, AMBER, RED")
    global CAUTION_MODE_RUNTIME
    CAUTION_MODE_RUNTIME = mode
    return CAUTION_MODE_RUNTIME


def apply_business_rules(event: ClaimEvent) -> List[str]:
    """
    Insurance-style business rules (MVP).
    These are not ML. They represent business guardrails / policy constraints.
    """
    hits: List[str] = []

    if event.customer_tenure_days < 30:
        hits.append("TENURE_LT_30D")

    if event.claim_amount >= 10000:
        hits.append("HIGH_AMOUNT_GTE_10K")

    if event.claim_amount >= 25000:
        hits.append("VERY_HIGH_AMOUNT_GTE_25K")

    if event.data_quality_score < 0.6:
        hits.append("LOW_DATA_QUALITY_LT_0_6")

    if (event.channel or "").upper() in {"PARTNER", "THIRD_PARTY"}:
        hits.append("CHANNEL_PARTNER")

    if (event.loss_type or "").upper() == "THEFT" and event.has_police_report == 0:
        hits.append("THEFT_NO_POLICE_REPORT")

    if event.document_count == 0:
        hits.append("NO_DOCUMENTS")

    if event.inconsistent_fields_flag == 1:
        hits.append("INCONSISTENT_FIELDS")

    return hits


def thresholds_for_mode(mode: str) -> Dict[str, float]:
    """
    Mode tunes automation aggressiveness.
    These are *automation thresholds*, independent of the model's learned threshold.
    """
    if mode == "GREEN":
        return {"approve_risk_max": 0.25, "approve_amount_max": 2500.0, "red_escalate_risk": 0.90}
    if mode == "AMBER":
        return {"approve_risk_max": 0.18, "approve_amount_max": 1800.0, "red_escalate_risk": 0.85}
    # RED
    return {"approve_risk_max": 0.12, "approve_amount_max": 1200.0, "red_escalate_risk": 0.80}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ----------------------------
# Model Service Calls
# ----------------------------
async def fetch_model_info_best_effort() -> None:
    """
    Try to populate model_version + operating threshold caches.
    If this fails, we still proceed (demo resilience), but /health will show degraded model.
    """
    global MODEL_VERSION_CACHE, MODEL_THRESHOLD_CACHE
    try:
        async with httpx.AsyncClient(timeout=MODEL_TIMEOUT_SECS) as client:
            r = await client.get(f"{MODEL_SERVICE_URL}/model/info")
            r.raise_for_status()
            payload = r.json()
            meta = payload.get("meta") or {}
            metrics = payload.get("metrics") or {}

            MODEL_VERSION_CACHE = meta.get("model_version") or meta.get("model_version", "unknown")
            # prefer meta operating threshold; fallback to metrics threshold
            MODEL_THRESHOLD_CACHE = meta.get("operating_threshold")
            if MODEL_THRESHOLD_CACHE is None:
                MODEL_THRESHOLD_CACHE = metrics.get("threshold")
    except Exception:
        # swallow; will be shown in /health via direct call
        return


async def model_predict(event: ClaimEvent) -> Dict[str, Any]:
    """
    Call the Model Service to compute risk_signal (fraud probability) + threshold + model_version.
    """
    req = {
        "claim_amount": event.claim_amount,
        "policy_limit": event.policy_limit,
        "deductible": event.deductible,
        "payment_method": event.payment_method or "ACH",
        "customer_tenure_days": event.customer_tenure_days,
        "customer_age_band": event.customer_age_band or "26_35",
        "policy_age_days": event.policy_age_days,
        "prior_claim_count_12m": event.prior_claim_count_12m,
        "prior_claim_amount_12m": event.prior_claim_amount_12m,
        "prior_fraud_flag": event.prior_fraud_flag,
        "loss_type": event.loss_type or "AUTO_COLLISION",
        "channel": event.channel or "MOBILE_APP",
        "region": event.region or "NJ",
        "incident_reported_delay_days": event.incident_reported_delay_days,
        "has_police_report": event.has_police_report,
        "document_count": event.document_count,
        "device_risk_score": event.device_risk_score,
        "ip_risk_score": event.ip_risk_score,
        "data_quality_score": event.data_quality_score,
        "missing_fields_count": event.missing_fields_count,
        "inconsistent_fields_flag": event.inconsistent_fields_flag,
        "submission_hour": event.submission_hour,
        "submission_day_of_week": event.submission_day_of_week,
    }

    async with httpx.AsyncClient(timeout=MODEL_TIMEOUT_SECS) as client:
        r = await client.post(f"{MODEL_SERVICE_URL}/predict", json=req)
        r.raise_for_status()
        return r.json()


# ----------------------------
# DB writes
# ----------------------------
def insert_event(cur, event: ClaimEvent, risk_signal: float, model_version: str, model_threshold: float):
    payload = {
        # original claim fields
        "claim_amount": event.claim_amount,
        "policy_limit": event.policy_limit,
        "deductible": event.deductible,
        "customer_tenure_days": event.customer_tenure_days,
        "customer_age_band": event.customer_age_band,
        "policy_age_days": event.policy_age_days,
        "prior_claim_count_12m": event.prior_claim_count_12m,
        "prior_claim_amount_12m": event.prior_claim_amount_12m,
        "prior_fraud_flag": event.prior_fraud_flag,
        "loss_type": event.loss_type,
        "channel": event.channel,
        "region": event.region,
        "payment_method": event.payment_method,
        "incident_reported_delay_days": event.incident_reported_delay_days,
        "has_police_report": event.has_police_report,
        "document_count": event.document_count,
        "device_risk_score": event.device_risk_score,
        "ip_risk_score": event.ip_risk_score,
        "data_quality_score": event.data_quality_score,
        "missing_fields_count": event.missing_fields_count,
        "inconsistent_fields_flag": event.inconsistent_fields_flag,
        "submission_hour": event.submission_hour,
        "submission_day_of_week": event.submission_day_of_week,
        # computed ML outputs
        "risk_signal": risk_signal,
        "model_threshold": model_threshold,
        "model_version": model_version,
    }

    cur.execute(
        """
        INSERT INTO events (event_id, event_time, domain, event_type, entity_id, payload)
        VALUES (%s,%s,%s,%s,%s,%s)
        ON CONFLICT (event_id) DO NOTHING
        """,
        (
            str(event.event_id),
            event.event_time,
            DOMAIN,
            EVENT_TYPE,
            event.entity_id,
            psycopg2.extras.Json(payload),
        ),
    )


def insert_decision(cur, decision: Dict[str, Any]):
    cur.execute(
        """
        INSERT INTO decision_events (
          decision_id, event_id, timestamp, entity_id, action, confidence,
          reason_codes, policy_version, model_version, outcome,
          latency_ms, business_impact, observability,
          caution_mode, rule_hits
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            decision["decision_id"],
            decision["event_id"],
            decision["timestamp"],
            decision["entity_id"],
            decision["action"],
            decision["confidence"],
            decision["reason_codes"],
            decision["policy_version"],
            decision["model_version"],
            decision["outcome"],
            decision["latency_ms"],
            psycopg2.extras.Json(decision["business_impact"]),
            psycopg2.extras.Json(decision["observability"]),
            decision["caution_mode"],
            decision["rule_hits"],
        ),
    )


# ----------------------------
# Routes
# ----------------------------
@app.on_event("startup")
async def startup():
    await fetch_model_info_best_effort()


@app.get("/health")
async def health():
    db_status = "ok"
    model_status = "ok"
    model_loaded = False
    model_detail = None

    # DB check
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
            _ = cur.fetchone()
    except Exception as e:
        db_status = "error"
        model_detail = f"db_error: {str(e)}"
    finally:
        try:
            conn.close()
        except Exception:
            pass

    # Model check
    try:
        async with httpx.AsyncClient(timeout=MODEL_TIMEOUT_SECS) as client:
            r = await client.get(f"{MODEL_SERVICE_URL}/health")
            r.raise_for_status()
            payload = r.json()
            model_loaded = bool(payload.get("model_loaded"))
            if not model_loaded:
                model_status = "degraded"
    except Exception as e:
        model_status = "error"
        model_detail = f"model_error: {str(e)}"

    return {
        "status": "ok" if (db_status == "ok" and model_status == "ok") else "degraded",
        "db": db_status,
        "model": model_status,
        "model_loaded": model_loaded,
        "mode": get_caution_mode(),
        "detail": model_detail,
    }


@app.get("/routes")
def routes():
    return [{"path": r.path, "name": r.name, "methods": list(r.methods)} for r in app.router.routes]


@app.get("/mode")
def get_mode():
    return {"caution_mode": get_caution_mode()}


@app.post("/mode")
def update_mode(payload: ModeUpdate):
    try:
        new_mode = set_caution_mode(payload.mode)
        return {"caution_mode": new_mode}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/process_claim", response_model=DecisionOut)
async def process_claim(event: ClaimEvent):
    start = time.time()
    mode = get_caution_mode()
    th = thresholds_for_mode(mode)

    # 1) Get model risk_signal
    try:
        pred = await model_predict(event)
        risk_signal = float(pred["risk_signal"])
        model_threshold = float(pred.get("threshold", 0.5))
        model_version = str(pred.get("model_version", "unknown"))
        # cache for convenience
        global MODEL_VERSION_CACHE, MODEL_THRESHOLD_CACHE
        MODEL_VERSION_CACHE = model_version
        MODEL_THRESHOLD_CACHE = model_threshold
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Model service unavailable or predict failed: {str(e)}"
        )

    # 2) Apply business rules
    rule_hits = apply_business_rules(event)

    # 3) Decision logic (mode + business rule aware) using ML risk_signal
    reasons: List[str] = []
    action: str
    confidence: float
    estimated_loss: float

    # Insurance-friendly “3-zone” framing:
    # - model_threshold is calibrated to FPR budget in training,
    # - we still add mode thresholds for automation safety.
    #
    # We interpret:
    # - risk_signal >= th['red_escalate_risk'] : HIGH risk (RED queue)
    # - risk_signal >= model_threshold         : suspicious (AMBER review)
    # - risk_signal < model_threshold          : likely legit (GREEN auto approve if safe)
    #
    # Business rules can override.

    # RED mode containment: route almost everything to review except extremely safe
    if mode == "RED":
        if rule_hits:
            action = "ROUTE_TO_REVIEW"
            confidence = 0.92
            reasons = ["CONTAINMENT_MODE"] + rule_hits
            estimated_loss = 2.0
        else:
            if risk_signal <= th["approve_risk_max"] and event.claim_amount <= th["approve_amount_max"]:
                action = "AUTO_APPROVE"
                confidence = 0.90
                reasons = ["VERY_LOW_RISK", "LOW_EXPOSURE"]
                estimated_loss = 0.0
            else:
                action = "ROUTE_TO_REVIEW"
                confidence = 0.86
                reasons = ["CONTAINMENT_MODE", "NOT_SAFE_ENOUGH"]
                estimated_loss = 2.0

    # AMBER mode: tighter automation; apply guardrails strictly
    elif mode == "AMBER":
        # If strong business guardrails, always review
        if any(h in rule_hits for h in ["TENURE_LT_30D", "HIGH_AMOUNT_GTE_10K", "LOW_DATA_QUALITY_LT_0_6", "CHANNEL_PARTNER", "THEFT_NO_POLICE_REPORT", "INCONSISTENT_FIELDS"]):
            action = "ROUTE_TO_REVIEW"
            confidence = 0.88
            reasons = ["CAUTION_MODE"] + rule_hits
            estimated_loss = 3.0
        else:
            if risk_signal >= th["red_escalate_risk"]:
                action = "ROUTE_TO_REVIEW"
                confidence = 0.90
                reasons = ["VERY_HIGH_MODEL_RISK"]
                estimated_loss = 12.0
            elif risk_signal >= model_threshold:
                action = "ROUTE_TO_REVIEW"
                confidence = 0.82
                reasons = ["SUSPICIOUS_BY_MODEL_THRESHOLD"]
                estimated_loss = 6.0
            else:
                # only auto approve if low risk AND low amount
                if risk_signal <= th["approve_risk_max"] and event.claim_amount <= th["approve_amount_max"]:
                    action = "AUTO_APPROVE"
                    confidence = 0.86
                    reasons = ["LOW_RISK_AMBER", "AMOUNT_OK_AMBER"]
                    estimated_loss = 0.0
                else:
                    action = "ROUTE_TO_REVIEW"
                    confidence = 0.78
                    reasons = ["NOT_SAFE_FOR_STP"]
                    estimated_loss = 4.0

    # GREEN mode: normal automation
    else:
        # Hard guardrails still apply
        if any(h in rule_hits for h in ["VERY_HIGH_AMOUNT_GTE_25K", "LOW_DATA_QUALITY_LT_0_6", "INCONSISTENT_FIELDS"]):
            action = "ROUTE_TO_REVIEW"
            confidence = 0.90
            reasons = ["BUSINESS_GUARDRAIL"] + rule_hits
            estimated_loss = 2.0
        else:
            if risk_signal >= th["red_escalate_risk"]:
                action = "ROUTE_TO_REVIEW"
                confidence = 0.90
                reasons = ["VERY_HIGH_MODEL_RISK"]
                estimated_loss = 15.0
            elif risk_signal >= model_threshold:
                action = "ROUTE_TO_REVIEW"
                confidence = 0.85
                reasons = ["SUSPICIOUS_BY_MODEL_THRESHOLD"]
                estimated_loss = 8.0
            else:
                # If low risk, allow straight-through processing (STP)
                if risk_signal <= th["approve_risk_max"] and event.claim_amount <= th["approve_amount_max"]:
                    action = "AUTO_APPROVE"
                    confidence = 0.92
                    reasons = ["LOW_RISK", "AMOUNT_OK"]
                    estimated_loss = 0.0
                else:
                    action = "ROUTE_TO_REVIEW"
                    confidence = 0.77
                    reasons = ["MEDIUM_RISK_POLICY"]
                    estimated_loss = 5.0

    latency_ms = int((time.time() - start) * 1000)
    decision_id = str(uuid4())
    now = utc_now()

    # Business impact is MVP estimate; later computed from KPI service with ground truth
    business_impact = {
        "estimated_loss_usd": float(estimated_loss),
        "estimated_savings_usd": 1.25 if action == "AUTO_APPROVE" else 0.25,
    }

    # Observability placeholder: later add trace_id/span_id/log_ref
    observability = {
        "model_service_url": MODEL_SERVICE_URL,
        "model_threshold": model_threshold,
    }

    decision = {
        "decision_id": decision_id,
        "event_id": str(event.event_id),
        "timestamp": now,  # stored as timestamptz by psycopg2
        "entity_id": event.entity_id,
        "action": action,
        "confidence": float(confidence),
        "reason_codes": reasons,
        "policy_version": POLICY_VERSION,
        "model_version": model_version,
        "caution_mode": mode,
        "rule_hits": rule_hits,
        "outcome": "SUCCESS",
        "latency_ms": latency_ms,
        "business_impact": business_impact,
        "observability": observability,
    }

    # Write to DB: raw event + decision card
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            insert_event(cur, event, risk_signal=risk_signal, model_version=model_version, model_threshold=model_threshold)
            insert_decision(cur, decision)
        conn.commit()
    finally:
        conn.close()

    return DecisionOut(
        decision_id=decision_id,
        event_id=str(event.event_id),
        timestamp=now.isoformat().replace("+00:00", "Z"),
        entity_id=event.entity_id,
        action=action,
        confidence=float(confidence),
        reason_codes=reasons,
        policy_version=POLICY_VERSION,
        model_version=model_version,
        caution_mode=mode,
        rule_hits=rule_hits,
        outcome="SUCCESS",
        latency_ms=latency_ms,
        business_impact=business_impact,
        risk_signal=risk_signal,
        model_threshold=model_threshold,
    )


@app.get("/decisions")
def list_decisions(limit: int = 50):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                  decision_id, event_id, timestamp, entity_id, action, confidence, reason_codes,
                  policy_version, model_version, caution_mode, rule_hits,
                  outcome, latency_ms, business_impact
                FROM decision_events
                ORDER BY timestamp DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()

        for r in rows:
            if isinstance(r.get("timestamp"), datetime):
                r["timestamp"] = r["timestamp"].isoformat().replace("+00:00", "Z")
        return rows
    finally:
        conn.close()