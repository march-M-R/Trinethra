from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from openai import OpenAI


def _client() -> Optional[OpenAI]:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        return None
    return OpenAI(api_key=key)


def embed(text: str) -> List[float]:
    client = _client()
    if client is None:
        # No embeddings possible without API key; return dummy vector (won't work for pgvector search)
        raise RuntimeError("OPENAI_API_KEY not set (embeddings required for RAG).")

    model = os.getenv("EMBED_MODEL", "text-embedding-3-small")
    resp = client.embeddings.create(model=model, input=text)
    return list(resp.data[0].embedding)


def generate_explanation(*, decision: Dict[str, Any], context: str) -> Dict[str, Any]:
    """
    Returns a structured object we can store + show in UI.
    If no OPENAI_API_KEY, caller should fall back to template mode.
    """
    client = _client()
    if client is None:
        raise RuntimeError("OPENAI_API_KEY not set (LLM generation optional but requested).")

    model = os.getenv("CHAT_MODEL", "gpt-4o-mini")

    system = (
        "You are an insurance underwriting assistant. "
        "Explain decisions in simple, audit-friendly language. "
        "DO NOT invent facts. Use only provided decision fields and the retrieved policy context."
    )

    user = f"""
Decision JSON:
{decision}

Retrieved policy context:
{context}

Return JSON with keys:
plain_english: string
key_reasons: array of strings
recommended_next_steps: array of strings
audit_note: string
"""

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )

    import json
    return json.loads(resp.choices[0].message.content)