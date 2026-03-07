# services/automation_api/app/db.py

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras


def get_db_conn():
    """
    Connect using DATABASE_URL, e.g.
    postgresql://trinethra_user:trinethra_pass@localhost:5432/trinethra
    """
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL not set")
    return psycopg2.connect(url)


def db_check() -> Dict[str, Any]:
    """Healthcheck used by /health/deps."""
    try:
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                cur.fetchone()
        finally:
            conn.close()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def insert_event(
    *,
    entity_id: str,
    payload: Dict[str, Any],
    domain: str = "claims",
    event_type: str = "claim_received",
    conn=None,
) -> str:
    """
    Matches your events table:

      event_id   uuid default uuid_generate_v4()
      event_time timestamptz default now()
      domain     text not null default 'claims'
      event_type text not null default 'claim_received'
      entity_id  text
      payload    jsonb not null
    """
    close_conn = False
    if conn is None:
        conn = get_db_conn()
        close_conn = True

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO events (domain, event_type, entity_id, payload)
                VALUES (%s, %s, %s, %s::jsonb)
                RETURNING event_id;
                """,
                (domain, event_type, entity_id, json.dumps(payload)),
            )
            event_id = cur.fetchone()[0]
        conn.commit()
        return str(event_id)
    finally:
        if close_conn:
            conn.close()


def insert_decision(
    *,
    event_id: str,
    action: str,
    confidence: float,
    caution_mode: str,
    risk_signal: float,
    threshold: float,
    model_version: str,
    policy_version: str,
    reason_codes: List[str],
    rule_hits: List[str],
    latency_ms: int,
    business_impact: Dict[str, Any],
    observability: Dict[str, Any],
    conn=None,
) -> None:
    """
    IMPORTANT:
    - reason_codes is text[]
    - rule_hits is text[]
    - business_impact, observability are jsonb
    """
    close_conn = False
    if conn is None:
        conn = get_db_conn()
        close_conn = True

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO decision_events (
                    event_id,
                    action,
                    confidence,
                    caution_mode,
                    risk_signal,
                    threshold,
                    model_version,
                    policy_version,
                    reason_codes,
                    rule_hits,
                    latency_ms,
                    business_impact,
                    observability
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    %s::text[], %s::text[], %s,
                    %s::jsonb, %s::jsonb
                );
                """,
                (
                    event_id,
                    action,
                    float(confidence),
                    caution_mode,
                    float(risk_signal),
                    float(threshold),
                    model_version,
                    policy_version,
                    reason_codes or [],
                    rule_hits or [],
                    int(latency_ms),
                    json.dumps(business_impact or {}),
                    json.dumps(observability or {}),
                ),
            )
        conn.commit()
    finally:
        if close_conn:
            conn.close()


def fetch_kpi_summary(window_hours: int = 24) -> Dict[str, Any]:
    conn = get_db_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                  COUNT(*) AS total,
                  AVG(d.risk_signal) AS avg_risk,
                  SUM(CASE WHEN d.action = 'AUTO_APPROVE' THEN 1 ELSE 0 END) AS auto_approve_count,
                  SUM(CASE WHEN d.action = 'ROUTE_TO_REVIEW' THEN 1 ELSE 0 END) AS review_count
                FROM decision_events d
                JOIN events e ON e.event_id = d.event_id
                WHERE e.event_time >= now() - (%s || ' hours')::interval;
                """,
                (int(window_hours),),
            )
            row = cur.fetchone() or {}

            total = int(row.get("total") or 0)
            auto_approve = int(row.get("auto_approve_count") or 0)
            review = int(row.get("review_count") or 0)

            summary = {
                "total": total,
                "avg_risk": float(row.get("avg_risk") or 0.0),
                "auto_approve_count": auto_approve,
                "review_count": review,
                "stp_rate": (auto_approve / total) if total else 0.0,
                "review_rate": (review / total) if total else 0.0,
            }

            # mode split from decision_events.caution_mode
            cur.execute(
                """
                SELECT caution_mode, COUNT(*) AS count
                FROM decision_events d
                JOIN events e ON e.event_id = d.event_id
                WHERE e.event_time >= now() - (%s || ' hours')::interval
                GROUP BY caution_mode
                ORDER BY count DESC;
                """,
                (int(window_hours),),
            )
            mode_split = cur.fetchall() or []

        return {"summary": summary, "mode_split": mode_split}
    finally:
        conn.close()


def fetch_top_rule_hits(window_hours: int = 24, limit: int = 10) -> Dict[str, Any]:
    conn = get_db_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    rh.rule AS rule,
                    COUNT(*) AS count
                FROM decision_events d
                JOIN events e ON e.event_id = d.event_id
                CROSS JOIN LATERAL unnest(d.rule_hits) AS rh(rule)
                WHERE e.event_time >= now() - (%s || ' hours')::interval
                GROUP BY rh.rule
                ORDER BY count DESC
                LIMIT %s;
                """,
                (int(window_hours), int(limit)),
            )
            items = cur.fetchall() or []
        return {"window_hours": int(window_hours), "items": items}
    finally:
        conn.close()


def fetch_recent_decisions(limit: int = 20) -> Dict[str, Any]:
    """
    We use events.event_time (exists) and decision_events columns.
    If your decision_events has 'timestamp' too, you can also return it,
    but this query will work regardless as long as d.event_id exists.
    """
    conn = get_db_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
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
                    d.latency_ms
                FROM decision_events d
                JOIN events e ON e.event_id = d.event_id
                ORDER BY e.event_time DESC
                LIMIT %s;
                """,
                (int(limit),),
            )
            rows = cur.fetchall() or []
        return {"items": rows}
    finally:
        conn.close()