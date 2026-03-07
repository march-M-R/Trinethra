from __future__ import annotations

import os
import time
from typing import Any, Dict

import requests
from fastapi import HTTPException

MODEL_ENDPOINT = os.getenv("MODEL_ENDPOINT", "http://localhost:8001/predict")
MODEL_TIMEOUT_SEC = float(os.getenv("MODEL_TIMEOUT_SEC", "5"))


def call_model(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calls model_service /predict with a guaranteed valid shape:
      { "payload": { ... } }

    - Uses json= (NOT data=)
    - On non-200: returns the real FastAPI 422 body (or raw text)
    """
    if not isinstance(payload, dict) or not payload:
        raise HTTPException(status_code=400, detail="payload must be a non-empty object")

    body = {"payload": payload}

    t0 = time.time()
    try:
        resp = requests.post(
            MODEL_ENDPOINT,
            json=body,
            timeout=MODEL_TIMEOUT_SEC,
        )
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"model-service request failed: {e}")

    latency_ms = int((time.time() - t0) * 1000)

    if resp.status_code != 200:
        try:
            detail = resp.json()
        except Exception:
            detail = resp.text
        raise HTTPException(
            status_code=502,
            detail=f"model-service call failed ({resp.status_code}): {detail}",
        )

    try:
        out = resp.json()
        out.setdefault("latency_ms", latency_ms)
        return out
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"bad model-service response JSON: {e}")