// ui/src/lib/api.ts

export type ProcessClaimRequest = {
  claim_id: string;
  policy_id: string;
  claim_type: string;
  amount: number;
  zip: string;
  incident_date: string;
  days_since_policy_start: number;
  age: number;
  years_with_insurer: number;
  previous_claims: number;
  channel: string;
  police_report_filed: boolean;
  injury_involved: boolean;
};

export type ProcessClaimResponse = {
  degraded?: boolean;
  warning?: string | null;
  action?: string;
  confidence?: number | null;
  reason_codes?: string[];
  rule_hits?: string[];
  caution_mode?: string;
  risk_signal?: number;
  threshold?: number;
  model_version?: string;
  latency_ms?: number;
  policy_version?: string;
  business_impact?: Record<string, unknown>;
  observability?: {
    llm_summary?: string;
    [key: string]: unknown;
  };
  llm_summary?: string;
  [key: string]: unknown;
};

export type DecisionRow = {
  id?: string;
  decision_id?: string;
  event_id?: string;
  claim_id?: string;
  action?: string;
  outcome?: string;
  decision?: string;
  score?: number;
  confidence?: number | null;
  risk_signal?: number;
  risk_score?: number;
  caution_mode?: string;
  mode?: string;
  model_version?: string;
  model?: string;
  policy_version?: string;
  latency_ms?: number;
  reason_codes?: string[];
  rule_hits?: string[];
  threshold?: number;
  created_at?: string;
  timestamp?: string;
  [key: string]: unknown;
};

export type KpiSummary = {
  total?: number;
  total_decisions?: number;
  approvals?: number;
  blocks?: number;
  reviews?: number;
  block_rate?: number;
  by_action?: Record<string, number>;
};

export type ExplanationResponse = {
  claim_id: string;
  summary: string;
  key_factors: string[];
  next_steps: string[];
  kpis_considered?: Record<string, unknown>;
};

export type AnalystResponse = { answer: string };

// Same-origin routes avoid cross-origin failures and keep service URLs server-side.
const AUTOMATION_BASE = "/api/automation";
const EXPLAIN_BASE = "/api/explain";

async function http<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
    signal: init?.signal ?? AbortSignal.timeout(60000),
  });

  const text = await res.text();
  const data = text ? safeJsonParse(text) : null;

  if (!res.ok) {
    const errorData =
      data && typeof data === "object"
        ? (data as { detail?: unknown; message?: unknown; error?: unknown })
        : null;
    const msg =
      (errorData && (errorData.detail || errorData.message || errorData.error)) ||
      text ||
      `${res.status} ${res.statusText}`;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }

  return (data as T) ?? ({} as T);
}

function safeJsonParse(s: string): unknown {
  try {
    return JSON.parse(s);
  } catch {
    return null;
  }
}

/**
 * Automation API: POST /process_claim
 * Sends the flat request body that the deployed backend expects.
 */
export async function processClaim(
  body: ProcessClaimRequest
): Promise<ProcessClaimResponse> {
  return http<ProcessClaimResponse>(`${AUTOMATION_BASE}/process_claim`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/**
 * Automation API: GET /decisions?limit=...
 * Backend may return an array directly or { items: [...] }.
 */
export async function getDecisions(limit = 50): Promise<DecisionRow[]> {
  const data = await http<unknown>(`${AUTOMATION_BASE}/decisions?limit=${limit}`);
  if (Array.isArray(data)) return data as DecisionRow[];
  if (data && typeof data === "object") {
    const wrapped = data as { items?: unknown; decisions?: unknown };
    if (Array.isArray(wrapped.items)) return wrapped.items as DecisionRow[];
    if (Array.isArray(wrapped.decisions)) return wrapped.decisions as DecisionRow[];
  }
  return [];
}

/**
 * Optional detail endpoint.
 * Returns null if your backend doesn't implement /decisions/{id}.
 */
export async function getDecisionById(id: string): Promise<DecisionRow | null> {
  return http<DecisionRow>(
    `${AUTOMATION_BASE}/decisions/${encodeURIComponent(id)}`
  );
}

/**
 * Automation API: GET /kpis
 * Uses automation service, not monitoring service.
 */
export async function getKpiSummary(windowHours = 24) {
  return http<KpiSummary>(`${AUTOMATION_BASE}/kpis?window_hours=${windowHours}`);
}

/**
 * Explain service: POST /explain/{claim_id}
 */
export async function getExplanation(
  claimId: string,
  payload: Record<string, unknown>,
  decision: Record<string, unknown>
) {
  return http<ExplanationResponse>(`${EXPLAIN_BASE}/explain/${encodeURIComponent(claimId)}`, {
    method: "POST",
    body: JSON.stringify({ payload, decision }),
  });
}

/**
 * Analyst endpoint
 */
export async function askAnalyst(
  question: string,
  context: {
    claim_id?: string;
    payload?: Record<string, unknown>;
    decision?: Record<string, unknown>;
  } = {}
) {
  return http<AnalystResponse>(`${EXPLAIN_BASE}/analyst`, {
    method: "POST",
    body: JSON.stringify({ question, ...context }),
  });
}
