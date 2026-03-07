from __future__ import annotations

import os
import time
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

try:
    from pydantic import ConfigDict
except Exception:  # pragma: no cover
    ConfigDict = None  # type: ignore

from .model_loader import get_model, predict_risk

app = FastAPI(title="Trinetra - Model Service", version="0.1.1")

FALLBACK_THRESHOLD = float(os.getenv("FALLBACK_THRESHOLD", "0.16"))
FALLBACK_MODEL_VERSION = os.getenv("FALLBACK_MODEL_VERSION", "stub-v0")
FALLBACK_BASE_RISK = float(os.getenv("FALLBACK_BASE_RISK", "0.55"))
FALLBACK_AMOUNT_SCALE = float(os.getenv("FALLBACK_AMOUNT_SCALE", "5000"))


class PredictRequest(BaseModel):
    if ConfigDict is not None:
        model_config = ConfigDict(extra="ignore", populate_by_name=True)

    features: Dict[str, Any] = Field(default_factory=dict, alias="payload")


class PredictResponse(BaseModel):
    risk_signal: float
    threshold: float
    model_version: str
    latency_ms: int
    degraded: bool = False
    warning: str | None = None


def _fallback_score(features: Dict[str, Any]) -> tuple[float, float, str, str]:
    amount = 0.0
    prev_claims = 0.0

    try:
        if "amount" in features:
            amount = float(features.get("amount") or 0.0)
        elif "claim_amount" in features:
            amount = float(features.get("claim_amount") or 0.0)
    except Exception:
        amount = 0.0

    try:
        if "previous_claims" in features:
            prev_claims = float(features.get("previous_claims") or 0.0)
        elif "num_prev_claims" in features:
            prev_claims = float(features.get("num_prev_claims") or 0.0)
    except Exception:
        prev_claims = 0.0

    risk = FALLBACK_BASE_RISK
    risk += min(max(amount / max(FALLBACK_AMOUNT_SCALE, 1.0), 0.0), 0.35)
    risk += min(max(prev_claims * 0.05, 0.0), 0.20)
    risk = max(0.01, min(0.99, risk))

    warning = "Model artifact failed to load; using fallback scorer."
    return risk, FALLBACK_THRESHOLD, FALLBACK_MODEL_VERSION, warning


@app.get("/health")
def health() -> Dict[str, Any]:
    try:
        _ = get_model()
        return {"status": "ok", "service": "model_service", "degraded": False}
    except Exception as e:
        return {
            "status": "ok",
            "service": "model_service",
            "degraded": True,
            "warning": f"model load failed: {e}",
        }


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest) -> PredictResponse:
    t0 = time.perf_counter()

    if not req.features or not isinstance(req.features, dict):
        raise HTTPException(
            status_code=422,
            detail='No features provided. Send JSON as either {"payload": {...}} or {"features": {...}}.',
        )

    try:
        risk, thr, ver = predict_risk(req.features)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return PredictResponse(
            risk_signal=float(risk),
            threshold=float(thr),
            model_version=str(ver),
            latency_ms=latency_ms,
            degraded=False,
            warning=None,
        )
    except Exception:
        risk, thr, ver, warn = _fallback_score(req.features)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return PredictResponse(
            risk_signal=float(risk),
            threshold=float(thr),
            model_version=str(ver),
            latency_ms=latency_ms,
            degraded=True,
            warning=warn,
        )