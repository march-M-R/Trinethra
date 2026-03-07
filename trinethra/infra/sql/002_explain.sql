-- Enable vector extension for embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- RAG chunks store: snippets you want the LLM to cite (policies, rule docs, etc.)
CREATE TABLE IF NOT EXISTS rag_chunks (
  chunk_id      uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  source        text NOT NULL,            -- e.g. "policy_handbook", "rules_doc"
  doc_id        text NOT NULL,            -- e.g. filename or logical id
  chunk_index   integer NOT NULL DEFAULT 0,
  content       text NOT NULL,
  metadata      jsonb NOT NULL DEFAULT '{}'::jsonb,
  embedding     vector(1536),             -- OpenAI 1536 dims (text-embedding-3-small) OR change if needed
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rag_chunks_source ON rag_chunks(source);
CREATE INDEX IF NOT EXISTS idx_rag_chunks_doc_id ON rag_chunks(doc_id);

-- optional: vector index (works best when you start doing similarity search)
-- Choose cosine distance typical for embeddings
CREATE INDEX IF NOT EXISTS idx_rag_chunks_embedding
ON rag_chunks
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Explanation output written by Layer 3
CREATE TABLE IF NOT EXISTS decision_explanations (
  explanation_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  event_id       uuid NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
  decision_id    uuid NULL REFERENCES decision_events(decision_id) ON DELETE CASCADE,
  entity_id      text NOT NULL,
  explanation    text NOT NULL,
  citations      jsonb NOT NULL DEFAULT '[]'::jsonb,
  model          text,
  latency_ms     integer,
  created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_decision_explanations_entity ON decision_explanations(entity_id);
CREATE INDEX IF NOT EXISTS idx_decision_explanations_created_at ON decision_explanations(created_at);