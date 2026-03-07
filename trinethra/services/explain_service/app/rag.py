from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple


def chunk_text(text: str, max_chars: int = 900, overlap: int = 150) -> List[str]:
    """
    Simple chunker for markdown/policy docs.
    """
    text = text.strip()
    if not text:
        return []
    chunks: List[str] = []
    i = 0
    while i < len(text):
        end = min(len(text), i + max_chars)
        chunk = text[i:end]
        chunks.append(chunk)
        if end == len(text):
            break
        i = max(0, end - overlap)
    return chunks


def build_prompt_context(citations: List[Dict[str, Any]]) -> str:
    """
    Create a compact context block from retrieved chunks.
    """
    lines = []
    for c in citations:
        lines.append(f"[{c['source']}#{c['chunk_index']} score={c['score']:.3f}] {c['content']}")
    return "\n\n".join(lines)


def key_reasons_from_decision(action: str, model_risk: float, threshold: float, rule_hits: List[str], reason_codes: List[str]) -> List[str]:
    reasons = []
    reasons.append(f"Model risk score is {model_risk:.3f} and threshold is {threshold:.3f}.")
    if rule_hits:
        reasons.append(f"Triggered rules: {', '.join(rule_hits)}.")
    if reason_codes:
        reasons.append(f"Reason codes: {', '.join(reason_codes)}.")
    if action == "ROUTE_TO_REVIEW":
        reasons.append("Claim routed to human review based on policy + risk signals.")
    else:
        reasons.append("Claim auto-approved as it falls within policy limits.")
    return reasons


def next_steps(action: str) -> List[str]:
    if action == "ROUTE_TO_REVIEW":
        return [
            "Send claim to an underwriter queue for manual review",
            "Verify supporting documents and police report (if applicable)",
            "Check claim amount justification and repair estimate"
        ]
    return [
        "Proceed with standard payment workflow",
        "Perform spot-check if required by internal SOP"
    ]