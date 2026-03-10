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
  action?: string;
  confidence?: number;
  reason_codes?: string[];
  rule_hits?: Record<string, unknown>;
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
  decision_id?: string;
  event_id?: string;
  claim_id?: string;
  action?: string;
  outcome?: string;
  decision?: string;
  score?: number;
  confidence?: number;
  risk_signal?: number;
  caution_mode?: string;
  mode?: string;
  model_version?: string;
  policy_version?: string;
  created_at?: string;
  timestamp?: string;
  [key: string]: unknown;
};

const AUTOMATION_BASE =
  process.env.NEXT_PUBLIC_AUTOMATION_API_BASE ??
  "https://trinethra-automation-api.onrender.com";

const EXPLAIN_BASE =
  process.env.NEXT_PUBLIC_EXPLAIN_API_BASE ??
  "https://trinethra-model-service.onrender.com";

async function http<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  const text = await res.text();
  const data = text ? safeJsonParse(text) : null;

  if (!res.ok) {
    const msg =
      (data && (data.detail || data.message || data.error)) ||
      text ||
      `${res.status} ${res.statusText}`;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }

  return (data as T) ?? ({} as T);
}

function safeJsonParse(s: string) {
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
  const data = await http<any>(`${AUTOMATION_BASE}/decisions?limit=${limit}`);
  if (Array.isArray(data)) return data as DecisionRow[];
  if (Array.isArray(data?.items)) return data.items as DecisionRow[];
  if (Array.isArray(data?.decisions)) return data.decisions as DecisionRow[];
  return [];
}

/**
 * Optional detail endpoint.
 * Returns null if your backend doesn't implement /decisions/{id}.
 */
export async function getDecisionById(id: string): Promise<DecisionRow | null> {
  try {
    return await http<DecisionRow>(
      `${AUTOMATION_BASE}/decisions/${encodeURIComponent(id)}`
    );
  } catch {
    return null;
  }
}

/**
 * Automation API: GET /kpis
 * Uses automation service, not monitoring service.
 */
export async function getKpiSummary(windowHours = 24) {
  void windowHours;
  return http<any>(`${AUTOMATION_BASE}/kpis`);
}

/**
 * Explain service: POST /explain/{claim_id}
 */
export async function getExplanation(
  claimId: string,
  payload: Record<string, any>,
  decision: Record<string, any>
) {
  return http<any>(`${EXPLAIN_BASE}/explain/${encodeURIComponent(claimId)}`, {
    method: "POST",
    body: JSON.stringify({ payload, decision }),
  });
}

/**
 * Analyst endpoint
 */
export async function askAnalyst(question: string) {
  return http<any>(`${EXPLAIN_BASE}/analyst`, {
    method: "POST",
    body: JSON.stringify({ question }),
  });
}