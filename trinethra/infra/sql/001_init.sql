CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS events (
  event_id      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  event_time    TIMESTAMPTZ NOT NULL DEFAULT now(),
  domain        TEXT NOT NULL DEFAULT 'claims',
  event_type    TEXT NOT NULL DEFAULT 'claim_received',
  entity_id     TEXT,
  payload       JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_event_time ON events (event_time);
CREATE INDEX IF NOT EXISTS idx_events_payload_gin ON events USING GIN (payload);

CREATE TABLE IF NOT EXISTS decision_events (
  decision_id     UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  event_id        UUID NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
  timestamp       TIMESTAMPTZ NOT NULL DEFAULT now(),

  action          TEXT NOT NULL,
  confidence      DOUBLE PRECISION NOT NULL,

  reason_codes    TEXT[] NOT NULL DEFAULT '{}',
  rule_hits       TEXT[] NOT NULL DEFAULT '{}',
  caution_mode    TEXT NOT NULL DEFAULT 'GREEN',

  risk_signal     DOUBLE PRECISION,
  threshold       DOUBLE PRECISION,
  model_version   TEXT,
  policy_version  TEXT,

  latency_ms      INTEGER,

  business_impact JSONB NOT NULL DEFAULT '{}'::jsonb,
  observability   JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_decisions_timestamp ON decision_events (timestamp);
CREATE INDEX IF NOT EXISTS idx_decisions_action ON decision_events (action);
CREATE INDEX IF NOT EXISTS idx_decisions_rulehits_gin ON decision_events USING GIN (rule_hits);