from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict

import psycopg2
import psycopg2.extras
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(title="Trinetra - Monitoring Service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _db_conn():
    host = os.getenv("DB_HOST", "localhost")
    port = int(os.getenv("DB_PORT", "5432"))
    db = os.getenv("DB_NAME", "trinethra")
    user = os.getenv("DB_USER", "trinethra_user")
    password = os.getenv("DB_PASSWORD", "trinethra_pass")

    return psycopg2.connect(
        host=host,
        port=port,
        dbname=db,
        user=user,
        password=password,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


def _window_start(window_hours: int) -> datetime:
    now = datetime.now(timezone.utc)
    return now - timedelta(hours=window_hours)


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "service": "monitoring_service"}


@app.get("/kpis/summary")
def kpis_summary(window_hours: int = Query(24, ge=1, le=24 * 30)) -> Dict[str, Any]:
    """
    Reads decision_events.timestamp (not events.event_time).
    """
    start_ts = _window_start(window_hours)

    sql = """
    WITH w AS (
      SELECT
        action,
        caution_mode,
        risk_signal,
        threshold
      FROM decision_events d
      WHERE d."timestamp" >= %(start_ts)s
    )
    SELECT
      (SELECT COUNT(*) FROM w) AS total_decisions,

      (SELECT COALESCE(jsonb_object_agg(action, cnt), '{}'::jsonb)
       FROM (SELECT action, COUNT(*) AS cnt FROM w GROUP BY action) a) AS by_action,

      (SELECT COALESCE(jsonb_object_agg(caution_mode, cnt), '{}'::jsonb)
       FROM (SELECT caution_mode, COUNT(*) AS cnt FROM w GROUP BY caution_mode) c) AS by_caution,

      (SELECT COALESCE(AVG(risk_signal), 0) FROM w) AS avg_risk_signal,
      (SELECT COALESCE(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY risk_signal), 0) FROM w) AS p95_risk_signal,
      (SELECT COALESCE(AVG(threshold), 0) FROM w) AS avg_threshold
    ;
    """

    try:
        with _db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {"start_ts": start_ts})
                row = cur.fetchone() or {}

        return {
            "window_hours": window_hours,
            "window_start_utc": start_ts.isoformat(),
            "total_decisions": int(row.get("total_decisions") or 0),
            "by_action": row.get("by_action") or {},
            "by_caution": row.get("by_caution") or {},
            "avg_risk_signal": float(row.get("avg_risk_signal") or 0),
            "p95_risk_signal": float(row.get("p95_risk_signal") or 0),
            "avg_threshold": float(row.get("avg_threshold") or 0),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"KPI summary failed: {e}")


@app.get("/kpis/decision_counts")
def kpis_decision_counts(window_hours: int = Query(24, ge=1, le=24 * 30)) -> Dict[str, Any]:
    start_ts = _window_start(window_hours)

    sql = """
    SELECT
      d.action,
      d.caution_mode,
      COUNT(*)::int AS count
    FROM decision_events d
    WHERE d."timestamp" >= %(start_ts)s
    GROUP BY d.action, d.caution_mode
    ORDER BY count DESC;
    """

    try:
        with _db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {"start_ts": start_ts})
                rows = cur.fetchall() or []

        return {
            "window_hours": window_hours,
            "window_start_utc": start_ts.isoformat(),
            "items": rows,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"KPI decision counts failed: {e}")