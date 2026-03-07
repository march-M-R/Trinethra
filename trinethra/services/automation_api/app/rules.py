from typing import Dict, Any, List


def compute_rule_hits(features: Dict[str, Any]) -> List[str]:
    hits = []

    amt = float(features.get("claim_amount", 0) or 0)
    claim_type = str(features.get("claim_type", "")).upper()
    police_report = bool(features.get("police_report", False))
    channel = str(features.get("channel", "")).upper()

    if amt >= 25000:
        hits.append("VERY_HIGH_AMOUNT_GTE_25K")
    elif amt >= 10000:
        hits.append("HIGH_AMOUNT_GTE_10K")

    if claim_type == "THEFT" and police_report is False:
        hits.append("THEFT_NO_POLICE_REPORT")

    if channel == "PARTNER":
        hits.append("CHANNEL_PARTNER")

    # Data quality guardrail example
    if "claim_amount" not in features or features.get("claim_amount") in (None, ""):
        hits.append("MISSING_CLAIM_AMOUNT")

    return hits