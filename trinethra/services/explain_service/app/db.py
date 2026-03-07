# services/explain_service/app/db.py

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

import psycopg
from psycopg.rows import dict_row

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()


def _require_db_url() -> str:
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL not set")
    return DATABASE_URL


def get_db_conn():
    """
    Returns a psycopg (v3) connection.
    Uses dict_row so fetches come back as dictionaries.
    """
    dsn = _require_db_url()
    return psycopg.connect(dsn, row_factory=dict_row)


def db_healthcheck() -> Dict[str, Any]:
    try:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 AS ok;")
                _ = cur.fetchone()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# -----------------------------
# RAG Chunks
# -----------------------------

def insert_rag_chunk(
    *,
    source: str,
    chunk_index: int,
    content: str,
    embedding: Optional[List[float]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Inserts a chunk into rag_chunks.
    - embedding can be None (allowed by schema)
    - metadata defaults to {}
    Returns chunk_id (uuid as string).
    """
    metadata = metadata or {}

    sql = """
    INSERT INTO rag_chunks (source, chunk_index, content, embedding, metadata)
    VALUES (%s, %s, %s, %s, %s::jsonb)
    RETURNING chunk_id::text;
    """

    # pgvector: you can pass embedding as Python list and cast to vector using ::vector
    # But easiest/most reliable: pass as string like '[0.1,0.2,...]'
    emb_value = None
    if embedding is not None:
        emb_value = "[" + ",".join(str(float(x)) for x in embedding) + "]"

    with get_db_conn() as conn:
        with conn.cursor() as cur:
            if emb_value is None:
                cur.execute(
                    """
                    INSERT INTO rag_chunks (source, chunk_index, content, metadata)
                    VALUES (%s, %s, %s, %s::jsonb)
                    RETURNING chunk_id::text;
                    """,
                    (source, chunk_index, content, psycopg.types.json.Jsonb(metadata)),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO rag_chunks (source, chunk_index, content, embedding, metadata)
                    VALUES (%s, %s, %s, %s::vector, %s::jsonb)
                    RETURNING chunk_id::text;
                    """,
                    (source, chunk_index, content, emb_value, psycopg.types.json.Jsonb(metadata)),
                )
            row = cur.fetchone()
            return row["chunk_id"]


def semantic_search_chunks(
    *,
    query_embedding: List[float],
    top_k: int = 5,
    source: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Semantic search using cosine distance:
      ORDER BY embedding <=> query_embedding
    Returns list of chunks with distance score.

    Requires:
      - pgvector extension
      - rag_chunks.embedding populated
    """
    if not query_embedding:
        return []

    q_emb = "[" + ",".join(str(float(x)) for x in query_embedding) + "]"

    base_sql = """
    SELECT
      chunk_id::text,
      source,
      chunk_index,
      content,
      metadata,
      (embedding <=> %s::vector) AS distance
    FROM rag_chunks
    WHERE embedding IS NOT NULL
    """

    params: List[Any] = [q_emb]

    if source:
        base_sql += " AND source = %s"
        params.append(source)

    base_sql += " ORDER BY embedding <=> %s::vector LIMIT %s;"
    params.extend([q_emb, int(top_k)])

    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(base_sql, params)
            rows = cur.fetchall()
            return rows  # dict_row -> list[dict]


# -----------------------------
# Decision Explanations
# -----------------------------

def insert_decision_explanation(
    *,
    decision_id: str,
    entity_id: str,
    explanation: Dict[str, Any],
) -> str:
    """
    Stores LLM explanation JSON into decision_explanations.
    Returns explanation_id (uuid as string).
    """
    sql = """
    INSERT INTO decision_explanations (decision_id, entity_id, explanation)
    VALUES (%s::uuid, %s, %s::jsonb)
    RETURNING explanation_id::text;
    """
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (decision_id, entity_id, psycopg.types.json.Jsonb(explanation)))
            row = cur.fetchone()
            return row["explanation_id"]


def fetch_latest_decision_context(entity_id: str) -> Optional[Dict[str, Any]]:
    """
    Pulls latest decision + event payload for a given entity_id.
    Helpful input to the explain service.

    Returns:
      {
        "decision_id": ...,
        "entity_id": ...,
        "event_time": ...,
        "action": ...,
        "confidence": ...,
        "risk_signal": ...,
        "threshold": ...,
        "model_version": ...,
        "policy_version": ...,
        "reason_codes": [...],
        "rule_hits": [...],
        "caution_mode": ...,
        "latency_ms": ...,
        "payload": {...}   # from events.payload
      }
    """
    sql = """
    SELECT
      d.decision_id::text AS decision_id,
      e.entity_id,
      e.event_time,
      d.action,
      d.confidence,
      d.risk_signal,
      d.threshold,
      d.model_version,
      d.policy_version,
      d.reason_codes,
      d.rule_hits,
      d.caution_mode,
      d.latency_ms,
      e.payload
    FROM decision_events d
    JOIN events e ON e.event_id = d.event_id
    WHERE e.entity_id = %s
    ORDER BY d.timestamp DESC
    LIMIT 1;
    """
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (entity_id,))
            row = cur.fetchone()
            return row