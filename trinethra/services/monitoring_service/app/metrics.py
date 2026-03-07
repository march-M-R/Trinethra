# services/monitoring_service/app/metrics.py

from __future__ import annotations

from typing import Any, Dict, List

from app.db import get_db_conn


def fetch_summary(window_hours: int = 24) -> Dict[str, Any]:
    """
    Returns basic summary KPIs computed from decision_events within the time window.
    """
    q = """
    SELECT
      COUNT(*)::int AS total,
      COALESCE(AVG(d.risk_signal), 0)::float AS avg_risk,
      SUM(CASE WHEN d.action = 'AUTO_APPROVE' THEN 1 ELSE 0 END)::int AS auto_approve_count,
      SUM(CASE WHEN d.action = 'ROUTE_TO_REVIEW' THEN 1 ELSE 0 END)::int AS review_count
    FROM decision_events d
    WHERE d.timestamp >= NOW() - (%s * INTERVAL '1 hour');
    """

    q_modes = """
    SELECT
      d.caution_mode,
      COUNT(*)::int AS count
    FROM decision_events d
    WHERE d.timestamp >= NOW() - (%s * INTERVAL '1 hour')
    GROUP BY d.caution_mode
    ORDER BY count DESC;
    """

    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(q, (window_hours,))
            total, avg_risk, auto_cnt, rev_cnt = cur.fetchone()

            stp_rate = (auto_cnt / total) if total else 0.0
            review_rate = (rev_cnt / total) if total else 0.0

            cur.execute(q_modes, (window_hours,))
            mode_rows = cur.fetchall()

    finally:
        conn.close()

    return {
        "total": int(total),
        "avg_risk": float(avg_risk),
        "auto_approve_count": int(auto_cnt),
        "review_count": int(rev_cnt),
        "stp_rate": float(stp_rate),
        "review_rate": float(review_rate),
        "mode_split": [{"caution_mode": r[0], "count": int(r[1])} for r in mode_rows],
    }


def fetch_rule_hits(window_hours: int = 24, limit: int = 10) -> Dict[str, Any]:
    """
    Counts occurrences of each rule in decision_events.rule_hits (text[]) for the time window.
    """
    q = """
    SELECT
      rule,
      COUNT(*)::int AS count
    FROM (
      SELECT unnest(d.rule_hits) AS rule
      FROM decision_events d
      WHERE d.timestamp >= NOW() - (%s * INTERVAL '1 hour')
    ) t
    GROUP BY rule
    ORDER BY count DESC
    LIMIT %s;
    """

    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(q, (window_hours, limit))
            rows = cur.fetchall()
    finally:
        conn.close()

    return {
        "window_hours": window_hours,
        "items": [{"rule": r[0], "count": int(r[1])} for r in rows],
    }


def fetch_recent_decisions(limit: int = 20) -> Dict[str, Any]:
    """
    Returns the most recent decisions joined to events to get entity_id + event_time.
    """
    q = """
    SELECT
      e.entity_id,
      e.event_time,
      d.action,
      d.caution_mode,
      d.risk_signal,
      d.threshold,
      d.model_version,
      d.policy_version,
      d.reason_codes,
      d.rule_hits,
      d.timestamp
    FROM decision_events d
    JOIN events e ON e.event_id = d.event_id
    ORDER BY d.timestamp DESC
    LIMIT %s;
    """

    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(q, (limit,))
            rows = cur.fetchall()
    finally:
        conn.close()

    items: List[Dict[str, Any]] = []
    for r in rows:
        items.append(
            {
                "entity_id": r[0],
                "event_time": r[1],
                "action": r[2],
                "caution_mode": r[3],
                "risk_signal": float(r[4] or 0.0),
                "threshold": float(r[5] or 0.0),
                "model_version": r[6],
                "policy_version": r[7],
                "reason_codes": r[8],  # text[]
                "rule_hits": r[9],     # text[]
                "timestamp": r[10],
            }
        )

    return {"items": items}