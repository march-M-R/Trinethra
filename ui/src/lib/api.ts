// ui/src/lib/api.ts

export type DecisioningEvent = {
  domain: string;
  event_type: string;
  entity_id: string;
  payload: Record<string, any>;
};

export type DecisionRow = {
  decision_id?: string;
  event_id?: string;
  claim_id?: string;
  action?: string;
  outcome?: string;
  decision?: string;
  score?: number;
  policy_version?: string;
  created_at?: string;
  [key: string]: unknown;
};

const AUTOMATION_BASE =
  process.env.NEXT_PUBLIC_AUTOMATION_API_BASE ?? "http://localhost:8003";

const MONITORING_BASE =
  process.env.NEXT_PUBLIC_MONITORING_API_BASE ?? "http://localhost:8004";

const EXPLAIN_BASE =
  process.env.NEXT_PUBLIC_EXPLAIN_API_BASE ?? "http://localhost:8001";

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
      (data && (data.detail || data.message)) ||
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
 */
export async function processClaim(event: DecisioningEvent) {
  return http<any>(`${AUTOMATION_BASE}/process_claim`, {
    method: "POST",
    body: JSON.stringify(event),
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
  return [];
}

/**
 * Automation API: GET /decisions/{id}
 */
export async function getDecisionById(id: string): Promise<DecisionRow> {
  return http<DecisionRow>(
    `${AUTOMATION_BASE}/decisions/${encodeURIComponent(id)}`
  );
}

/**
 * Monitoring API: GET /kpis/summary?window_hours=...
 */
export async function getKpiSummary(windowHours = 24) {
  return http<any>(
    `${MONITORING_BASE}/kpis/summary?window_hours=${windowHours}`
  );
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
 * Kept environment-based for production safety.
 */
export async function askAnalyst(question: string) {
  return http<any>(`${EXPLAIN_BASE}/analyst`, {
    method: "POST",
    body: JSON.stringify({ question }),
  });
}