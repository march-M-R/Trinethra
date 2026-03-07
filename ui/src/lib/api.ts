// ui/src/lib/api.ts

export type DecisioningEvent = {
  domain: string;
  event_type: string;
  entity_id: string;
  payload: Record<string, any>;
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

  // Try to parse body even on errors (FastAPI returns JSON detail)
  const text = await res.text();
  const data = text ? safeJsonParse(text) : null;

  if (!res.ok) {
    const msg =
      (data && (data.detail || data.message)) ||
      `${res.status} ${res.statusText}`;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }

  // If endpoint returns empty body, return empty object
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
 * ✅ Automation API: POST /process_claim
 */
export async function processClaim(event: DecisioningEvent) {
  return http<any>(`${AUTOMATION_BASE}/process_claim`, {
    method: "POST",
    body: JSON.stringify(event),
  });
}

/**
 * ✅ Automation API: GET /decisions?limit=...
 * Your backend returns: { items: [...] }
 * UI expects an array → normalize here.
 */
export async function getDecisions(limit = 50) {
  const data = await http<any>(`${AUTOMATION_BASE}/decisions?limit=${limit}`);
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.items)) return data.items;
  return [];
}

/**
 * ✅ Automation API: GET /decisions/{id}
 */
export async function getDecisionById(id: string) {
  return http<any>(`${AUTOMATION_BASE}/decisions/${encodeURIComponent(id)}`);
}

/**
 * ✅ Monitoring API: GET /kpis/summary?window_hours=...
 */
export async function getKpiSummary(windowHours = 24) {
  return http<any>(
    `${MONITORING_BASE}/kpis/summary?window_hours=${windowHours}`
  );
}

/**
 * ✅ Explain service: POST /explain/{claim_id}
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
export async function askAnalyst(question: string) {
  const res = await fetch("http://localhost:8001/analyst", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ question }),
  });

  return res.json();
}