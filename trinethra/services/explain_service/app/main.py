from __future__ import annotations

import os
from typing import Any, Dict, List

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="Trinetra - Explain Service", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MONITORING_BASE = os.getenv("MONITORING_BASE", "http://127.0.0.1:8004")


class ExplainRequest(BaseModel):
    payload: Dict[str, Any] = Field(default_factory=dict)
    decision: Dict[str, Any] = Field(default_factory=dict)


def _safe_num(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def _safe_int(x: Any, default: int = 0) -> int:
    try:
        return int(float(x))
    except Exception:
        return default


def _fetch_kpis(window_hours: int = 24) -> Dict[str, Any]:
    try:
        r = requests.get(
            f"{MONITORING_BASE}/kpis/summary",
            params={"window_hours": window_hours},
            timeout=5,
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass

    return {
        "total_decisions": 0,
        "by_action": {},
        "avg_risk_signal": 0,
        "p95_risk_signal": 0,
    }


def _build_key_factors(payload: Dict[str, Any], decision: Dict[str, Any]) -> List[str]:
    factors: List[str] = []

    amount = _safe_num(payload.get("amount"), 0)
    prev_claims = _safe_int(payload.get("previous_claims"), 0)
    days_since = _safe_int(payload.get("days_since_policy_start"), 0)
    police = bool(payload.get("police_report_filed", False))
    injury = bool(payload.get("injury_involved", False))
    risk = _safe_num(decision.get("risk_signal"), 0)

    if amount >= 1000:
        factors.append(f"Claim amount of ${amount:,.0f} is material enough to warrant scrutiny.")
    if prev_claims >= 2:
        factors.append(f"Previous claims count is {prev_claims}, which increases review sensitivity.")
    if 0 < days_since <= 30:
        factors.append("Claim occurred shortly after policy inception, which can indicate higher risk.")
    if not police and amount >= 1000:
        factors.append("No police report is available despite a non-trivial claim amount.")
    if injury:
        factors.append("Injury involvement increases case complexity and review need.")
    if risk >= 0.70:
        factors.append(f"Predicted fraud risk score is elevated at {risk:.3f}.")

    if not factors:
        factors.append("No dominant red flag was detected beyond the model score and policy thresholds.")

    return factors


def _build_next_steps(action: str) -> List[str]:
    action = (action or "").upper()

    if action == "AUTO_APPROVE":
        return [
            "Proceed with standard claim validation and settlement workflow.",
            "Verify uploaded documents are complete before payout.",
        ]

    if action == "BLOCK":
        return [
            "Escalate the case to fraud investigation / SIU.",
            "Hold payout until identity, documentation, and incident details are validated.",
        ]

    return [
        "Route the claim to a human adjuster for manual review.",
        "Validate supporting documents, prior-claim history, and incident consistency before settlement.",
    ]


def _build_summary(payload: Dict[str, Any], decision: Dict[str, Any], kpis: Dict[str, Any]) -> str:
    action = (decision.get("action") or "UNKNOWN").upper()
    risk = _safe_num(decision.get("risk_signal"), 0)
    confidence = _safe_num(decision.get("confidence"), 0)

    total_decisions = _safe_int(kpis.get("total_decisions"), 0)
    by_action = kpis.get("by_action") or {}
    blocks = _safe_int(by_action.get("BLOCK"), 0)
    block_rate = (blocks / total_decisions * 100) if total_decisions > 0 else 0
    avg_risk = _safe_num(kpis.get("avg_risk_signal"), 0)

    if action == "AUTO_APPROVE":
        return (
            f"This claim was automatically approved because its fraud risk score of {risk:.3f} "
            f"falls within the safe approval range, with model confidence of {confidence:.2f}. "
            f"In the current monitoring window, the platform has processed {total_decisions} claims "
            f"with an average risk score of {avg_risk:.3f}. Based on both claim-level and recent platform-level "
            f"signals, the case can proceed through standard settlement checks."
        )

    if action == "BLOCK":
        return (
            f"This claim was automatically blocked because its fraud risk score of {risk:.3f} "
            f"exceeds the blocking threshold, with model confidence of {confidence:.2f}. "
            f"In the current monitoring window, the platform has processed {total_decisions} claims "
            f"and is currently blocking {block_rate:.2f}% of them, indicating active fraud control. "
            f"Given both the claim-level score and the current portfolio risk posture, escalation for investigation is appropriate."
        )

    return (
        f"This claim has been routed to manual review because its fraud risk score of {risk:.3f} "
        f"falls within the review band, with model confidence of {confidence:.2f}. "
        f"In the current monitoring window, the platform has processed {total_decisions} claims, "
        f"with a block rate of {block_rate:.2f}% and an average risk score of {avg_risk:.3f}. "
        f"Given the elevated claim-level risk and current platform-wide risk posture, human validation is recommended before settlement."
    )


@app.get("/health")
def health():
    return {"status": "ok", "service": "explain_service"}


@app.post("/explain/{claim_id}")
def explain_claim(claim_id: str, req: ExplainRequest):
    try:
        payload = req.payload or {}
        decision = req.decision or {}

        kpis = _fetch_kpis(window_hours=24)
        summary = _build_summary(payload, decision, kpis)
        key_factors = _build_key_factors(payload, decision)
        next_steps = _build_next_steps(decision.get("action", ""))

        return {
            "claim_id": claim_id,
            "summary": summary,
            "key_factors": key_factors,
            "next_steps": next_steps,
            "kpis_considered": {
                "total_decisions": kpis.get("total_decisions", 0),
                "by_action": kpis.get("by_action", {}),
                "avg_risk_signal": kpis.get("avg_risk_signal", 0),
                "p95_risk_signal": kpis.get("p95_risk_signal", 0),
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Explain failed: {e}")