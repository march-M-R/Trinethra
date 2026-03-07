from pydantic import BaseModel, Field
from typing import Optional, Dict, Any


class ClaimFeatures(BaseModel):
    features: Dict[str, Any] = Field(..., description="Flat key/value claim features")


class PredictResponse(BaseModel):
    risk_signal: float = Field(..., ge=0.0, le=1.0)
    threshold: float = Field(..., ge=0.0, le=1.0)
    model_version: str
    latency_ms: int


class ModelInfoResponse(BaseModel):
    model_version: str
    threshold: float
    metrics: Optional[Dict[str, Any]] = None
    feature_schema: Optional[list[str]] = None