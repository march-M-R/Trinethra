# services/automation_api/app/schemas.py

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ClaimIn(BaseModel):
    entity_id: str = Field(..., examples=["CLM-8001"])
    features: Dict[str, Any] = Field(default_factory=dict)


class DecisionCard(BaseModel):
    action: str
    confidence: float
    reason_codes: List[str] = Field(default_factory=list)
    rule_hits: List[str] = Field(default_factory=list)
    caution_mode: str
    risk_signal: float
    threshold: float
    model_version: str
    latency_ms: int
    policy_version: str
    business_impact: Dict[str, Any] = Field(default_factory=dict)
    observability: Dict[str, Any] = Field(default_factory=dict)