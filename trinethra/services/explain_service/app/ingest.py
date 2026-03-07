from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Any

from dotenv import load_dotenv

from app.rag import chunk_text
from app.db import upsert_rag_chunk
from app.llm import embed

load_dotenv()

POLICY_DIR = Path(os.getenv("POLICY_DIR", "policy_docs"))


def ingest():
    if not POLICY_DIR.exists():
        raise RuntimeError(f"POLICY_DIR not found: {POLICY_DIR.resolve()}")

    for file in POLICY_DIR.glob("*.md"):
        text = file.read_text(encoding="utf-8")
        chunks = chunk_text(text)
        for idx, chunk in enumerate(chunks):
            vec = embed(chunk)
            meta: Dict[str, Any] = {"filename": file.name}
            upsert_rag_chunk(source=file.name, chunk_index=idx, content=chunk, embedding=vec, metadata=meta)
        print(f"✅ Ingested {file.name} chunks={len(chunks)}")


if __name__ == "__main__":
    ingest()