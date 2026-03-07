from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ExplainRequest(BaseModel):
    entity_id: str = Field(..., examples=["CLM-9001"])
    top_k: int = 5


class RagCitation(BaseModel):
    source: str
    chunk_id: str
    chunk_index: int
    score: float


class ExplainResponse(BaseModel):
    entity_id: str
    decision_id: Optional[str] = None
    action: str
    risk_signal: float
    threshold: float
    confidence: float
    caution_mode: str
    reason_codes: List[str]
    rule_hits: List[str]

    plain_english: str
    key_reasons: List[str]
    recommended_next_steps: List[str]
    audit_note: str

    citations: List[RagCitation] = []
    raw: Dict[str, Any] = {}