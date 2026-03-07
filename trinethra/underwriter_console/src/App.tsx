import { useEffect, useMemo, useState } from "react";

const API_AUTOMATION = "http://localhost:8002";
const API_MONITORING = "http://localhost:8003";

type ClaimFeatures = {
  claim_amount: number;
  claim_type: string;
  police_report: boolean;
  channel: string;
};

type ClaimRequest = {
  entity_id: string;
  features: ClaimFeatures;
};

type DecisionResponse = {
  action: string;
  confidence: number;
  reason_codes: string[];
  rule_hits: string[];
  caution_mode: string;
  risk_signal: number;
  threshold: number;
  model_version: string;
  latency_ms: number;
  policy_version: string;
  business_impact?: Record<string, any>;
  observability?: Record<string, any>;
};

type KpiSummary = {
  total: number;
  avg_risk: number;
  stp_rate: number;
  review_rate: number;
};

type RecentDecision = {
  entity_id: string;
  event_time: string;
  timestamp: string;
  action: string;
  caution_mode: string;
  risk_signal: number;
  threshold: number;
  model_version: string;
  policy_version: string;
  reason_codes: string[];
  rule_hits: string[];
};

function num(v: any, fallback = 0) {
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}

function badgeStyle(kind: "GREEN" | "AMBER" | "RED") {
  const base: React.CSSProperties = {
    display: "inline-block",
    padding: "6px 10px",
    borderRadius: 999,
    fontSize: 12,
    fontWeight: 700,
    border: "1px solid rgba(0,0,0,0.12)",
  };
  if (kind === "GREEN") return { ...base, background: "rgba(46, 204, 113, 0.15)" };
  if (kind === "AMBER") return { ...base, background: "rgba(241, 196, 15, 0.20)" };
  return { ...base, background: "rgba(231, 76, 60, 0.18)" };
}

function actionStyle(action: string) {
  const a = (action || "").toUpperCase();
  const base: React.CSSProperties = {
    display: "inline-block",
    padding: "8px 12px",
    borderRadius: 12,
    fontSize: 13,
    fontWeight: 800,
    border: "1px solid rgba(0,0,0,0.14)",
  };
  if (a.includes("APPROVE")) return { ...base, background: "rgba(46, 204, 113, 0.15)" };
  if (a.includes("REVIEW")) return { ...base, background: "rgba(241, 196, 15, 0.20)" };
  if (a.includes("DENY") || a.includes("REJECT")) return { ...base, background: "rgba(231, 76, 60, 0.18)" };
  return { ...base, background: "rgba(52, 152, 219, 0.12)" };
}

export default function App() {
  // -----------------------------
  // Form state
  // -----------------------------
  const [entityId, setEntityId] = useState<string>(() => `CLM-${Math.floor(Math.random() * 9000 + 1000)}`);
  const [claimAmount, setClaimAmount] = useState<number>(800);
  const [claimType, setClaimType] = useState<string>("COLLISION");
  const [policeReport, setPoliceReport] = useState<boolean>(true);
  const [channel, setChannel] = useState<string>("DIRECT");

  // -----------------------------
  // API state
  // -----------------------------
  const [decision, setDecision] = useState<DecisionResponse | null>(null);
  const [kpis, setKpis] = useState<KpiSummary | null>(null);
  const [recent, setRecent] = useState<RecentDecision[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [err, setErr] = useState<string>("");

  const requestBody: ClaimRequest = useMemo(
    () => ({
      entity_id: entityId.trim(),
      features: {
        claim_amount: num(claimAmount, 0),
        claim_type: claimType.trim(),
        police_report: Boolean(policeReport),
        channel: channel.trim(),
      },
    }),
    [entityId, claimAmount, claimType, policeReport, channel]
  );

  const canSubmit = useMemo(() => {
    if (!requestBody.entity_id) return false;
    if (!requestBody.features.claim_type) return false;
    if (!requestBody.features.channel) return false;
    if (!Number.isFinite(requestBody.features.claim_amount) || requestBody.features.claim_amount < 0) return false;
    return true;
  }, [requestBody]);

  async function fetchJson(url: string, init?: RequestInit) {
    const res = await fetch(url, init);
    const txt = await res.text();
    if (!res.ok) {
      // try JSON error
      try {
        const j = JSON.parse(txt);
        throw new Error(j?.detail ? String(j.detail) : `${res.status} ${res.statusText}`);
      } catch {
        throw new Error(txt || `${res.status} ${res.statusText}`);
      }
    }
    try {
      return JSON.parse(txt);
    } catch {
      return txt;
    }
  }

  async function refreshMonitoring() {
    try {
      const s = await fetchJson(`${API_MONITORING}/kpis/summary?window_hours=24`);
      setKpis({
        total: num(s.total),
        avg_risk: num(s.avg_risk),
        stp_rate: num(s.stp_rate),
        review_rate: num(s.review_rate),
      });

      const r = await fetchJson(`${API_MONITORING}/decisions/recent?limit=10`);
      setRecent(Array.isArray(r.items) ? r.items : []);
    } catch (e: any) {
      // monitoring optional; don’t hard-fail the app
      console.error("monitoring refresh failed:", e?.message || e);
    }
  }

  async function submit() {
    setErr("");
    setDecision(null);
    setLoading(true);

    try {
      const data = await fetchJson(`${API_AUTOMATION}/process_claim`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestBody),
      });
      setDecision(data as DecisionResponse);

      // refresh monitoring after a new decision
      await refreshMonitoring();
    } catch (e: any) {
      setErr(e?.message || "Request failed");
    } finally {
      setLoading(false);
    }
  }

  function loadExample(example: "low" | "partner" | "theft_no_police" | "very_high") {
    setDecision(null);
    setErr("");

    if (example === "low") {
      setEntityId(`CLM-${Math.floor(Math.random() * 9000 + 1000)}`);
      setClaimAmount(800);
      setClaimType("COLLISION");
      setPoliceReport(true);
      setChannel("DIRECT");
      return;
    }
    if (example === "partner") {
      setEntityId(`CLM-${Math.floor(Math.random() * 9000 + 1000)}`);
      setClaimAmount(2500);
      setClaimType("COLLISION");
      setPoliceReport(true);
      setChannel("PARTNER");
      return;
    }
    if (example === "theft_no_police") {
      setEntityId(`CLM-${Math.floor(Math.random() * 9000 + 1000)}`);
      setClaimAmount(12000);
      setClaimType("THEFT");
      setPoliceReport(false);
      setChannel("PARTNER");
      return;
    }
    // very_high
    setEntityId(`CLM-${Math.floor(Math.random() * 9000 + 1000)}`);
    setClaimAmount(40000);
    setClaimType("THEFT");
    setPoliceReport(false);
    setChannel("DIRECT");
  }

  useEffect(() => {
    refreshMonitoring();
  }, []);

  const container: React.CSSProperties = {
    minHeight: "100vh",
    padding: 28,
    background: "#0b1220",
    color: "white",
    fontFamily: "Inter, system-ui, Arial",
  };

  const card: React.CSSProperties = {
    background: "rgba(255,255,255,0.06)",
    border: "1px solid rgba(255,255,255,0.12)",
    borderRadius: 16,
    padding: 18,
    boxShadow: "0 12px 40px rgba(0,0,0,0.25)",
  };

  const label: React.CSSProperties = { fontSize: 12, opacity: 0.85, marginBottom: 6 };
  const input: React.CSSProperties = {
    width: "100%",
    padding: "10px 12px",
    borderRadius: 12,
    border: "1px solid rgba(255,255,255,0.14)",
    background: "rgba(0,0,0,0.25)",
    color: "white",
    outline: "none",
  };

  const btn: React.CSSProperties = {
    padding: "10px 14px",
    borderRadius: 12,
    border: "1px solid rgba(255,255,255,0.16)",
    background: "rgba(255,255,255,0.10)",
    color: "white",
    cursor: "pointer",
    fontWeight: 700,
  };

  const btnPrimary: React.CSSProperties = {
    ...btn,
    background: "rgba(52,152,219,0.25)",
    border: "1px solid rgba(52,152,219,0.40)",
  };

  const grid: React.CSSProperties = {
    display: "grid",
    gridTemplateColumns: "1.1fr 0.9fr",
    gap: 18,
    alignItems: "start",
    marginTop: 18,
  };

  return (
    <div style={container}>
      <div style={{ maxWidth: 1150, margin: "0 auto" }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 16, alignItems: "center" }}>
          <div>
            <h1 style={{ margin: 0, fontSize: 26, letterSpacing: 0.2 }}>Trinethra Underwriter Console</h1>
            <div style={{ marginTop: 6, opacity: 0.85, fontSize: 13 }}>
              Layer 1 (Automation) → Layer 2 (Monitoring) → UI
            </div>
          </div>

          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <button style={btn} onClick={() => loadExample("low")}>Load Low-Risk</button>
            <button style={btn} onClick={() => loadExample("partner")}>Load Partner</button>
            <button style={btn} onClick={() => loadExample("theft_no_police")}>Load Theft No Police</button>
            <button style={btn} onClick={() => loadExample("very_high")}>Load Very High</button>
          </div>
        </div>

        <div style={grid}>
          {/* LEFT: Claim intake + decision */}
          <div style={{ display: "grid", gap: 18 }}>
            <div style={card}>
              <h2 style={{ margin: 0, fontSize: 18 }}>Claim Intake</h2>
              <div style={{ marginTop: 14, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
                <div>
                  <div style={label}>Entity ID</div>
                  <input
                    style={input}
                    value={entityId}
                    onChange={(e) => setEntityId(e.target.value)}
                    placeholder="CLM-9001"
                  />
                </div>

                <div>
                  <div style={label}>Claim Amount</div>
                  <input
                    style={input}
                    type="number"
                    value={claimAmount}
                    onChange={(e) => setClaimAmount(num(e.target.value))}
                    min={0}
                  />
                </div>

                <div>
                  <div style={label}>Claim Type</div>
                  <select
                    style={input}
                    value={claimType}
                    onChange={(e) => setClaimType(e.target.value)}
                  >
                    <option value="COLLISION">COLLISION</option>
                    <option value="THEFT">THEFT</option>
                    <option value="FIRE">FIRE</option>
                    <option value="WATER_DAMAGE">WATER_DAMAGE</option>
                    <option value="LIABILITY">LIABILITY</option>
                  </select>
                </div>

                <div>
                  <div style={label}>Channel</div>
                  <select
                    style={input}
                    value={channel}
                    onChange={(e) => setChannel(e.target.value)}
                  >
                    <option value="DIRECT">DIRECT</option>
                    <option value="PARTNER">PARTNER</option>
                    <option value="AGENT">AGENT</option>
                  </select>
                </div>

                <div style={{ gridColumn: "1 / -1", display: "flex", alignItems: "center", gap: 10 }}>
                  <input
                    type="checkbox"
                    checked={policeReport}
                    onChange={(e) => setPoliceReport(e.target.checked)}
                    style={{ width: 18, height: 18 }}
                  />
                  <div style={{ opacity: 0.9 }}>Police report present</div>
                </div>

                <div style={{ gridColumn: "1 / -1", display: "flex", gap: 10, alignItems: "center" }}>
                  <button
                    style={btnPrimary}
                    onClick={submit}
                    disabled={!canSubmit || loading}
                  >
                    {loading ? "Processing..." : "Run Decision"}
                  </button>

                  <button style={btn} onClick={refreshMonitoring}>
                    Refresh Monitoring
                  </button>

                  <div style={{ marginLeft: "auto", opacity: 0.8, fontSize: 12 }}>
                    POST {API_AUTOMATION}/process_claim
                  </div>
                </div>

                {err && (
                  <div style={{ gridColumn: "1 / -1", padding: 12, borderRadius: 12, background: "rgba(231, 76, 60, 0.15)", border: "1px solid rgba(231,76,60,0.35)" }}>
                    <b>Error:</b> {err}
                  </div>
                )}

                <div style={{ gridColumn: "1 / -1" }}>
                  <div style={{ ...label, marginBottom: 8 }}>Request Payload</div>
                  <pre style={{ margin: 0, padding: 12, borderRadius: 12, background: "rgba(0,0,0,0.35)", overflowX: "auto", fontSize: 12 }}>
                    {JSON.stringify(requestBody, null, 2)}
                  </pre>
                </div>
              </div>
            </div>

            <div style={card}>
              <h2 style={{ margin: 0, fontSize: 18 }}>Decision Output</h2>

              {!decision ? (
                <div style={{ marginTop: 12, opacity: 0.75 }}>
                  Run a decision to see output here.
                </div>
              ) : (
                <div style={{ marginTop: 14, display: "grid", gap: 12 }}>
                  <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
                    <span style={actionStyle(decision.action)}>{decision.action}</span>
                    <span style={badgeStyle((decision.caution_mode || "GREEN") as any)}>
                      {decision.caution_mode}
                    </span>
                    <span style={{ opacity: 0.8, fontSize: 12 }}>
                      policy: {decision.policy_version} • model: {decision.model_version}
                    </span>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
                    <div style={{ padding: 12, borderRadius: 12, background: "rgba(0,0,0,0.25)" }}>
                      <div style={label}>Risk Signal</div>
                      <div style={{ fontSize: 18, fontWeight: 800 }}>{decision.risk_signal.toFixed(4)}</div>
                    </div>
                    <div style={{ padding: 12, borderRadius: 12, background: "rgba(0,0,0,0.25)" }}>
                      <div style={label}>Threshold</div>
                      <div style={{ fontSize: 18, fontWeight: 800 }}>{decision.threshold.toFixed(4)}</div>
                    </div>
                    <div style={{ padding: 12, borderRadius: 12, background: "rgba(0,0,0,0.25)" }}>
                      <div style={label}>Confidence</div>
                      <div style={{ fontSize: 18, fontWeight: 800 }}>{decision.confidence.toFixed(2)}</div>
                    </div>
                    <div style={{ padding: 12, borderRadius: 12, background: "rgba(0,0,0,0.25)" }}>
                      <div style={label}>Latency</div>
                      <div style={{ fontSize: 18, fontWeight: 800 }}>{decision.latency_ms} ms</div>
                    </div>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                    <div style={{ padding: 12, borderRadius: 12, background: "rgba(0,0,0,0.25)" }}>
                      <div style={label}>Reason Codes</div>
                      {decision.reason_codes?.length ? (
                        <ul style={{ margin: "6px 0 0 18px" }}>
                          {decision.reason_codes.map((r, i) => (
                            <li key={i} style={{ marginBottom: 4 }}>{r}</li>
                          ))}
                        </ul>
                      ) : (
                        <div style={{ opacity: 0.75 }}>None</div>
                      )}
                    </div>

                    <div style={{ padding: 12, borderRadius: 12, background: "rgba(0,0,0,0.25)" }}>
                      <div style={label}>Rule Hits</div>
                      {decision.rule_hits?.length ? (
                        <ul style={{ margin: "6px 0 0 18px" }}>
                          {decision.rule_hits.map((r, i) => (
                            <li key={i} style={{ marginBottom: 4 }}>{r}</li>
                          ))}
                        </ul>
                      ) : (
                        <div style={{ opacity: 0.75 }}>None</div>
                      )}
                    </div>
                  </div>

                  <details style={{ marginTop: 4 }}>
                    <summary style={{ cursor: "pointer", opacity: 0.9 }}>Raw response (debug)</summary>
                    <pre style={{ marginTop: 10, padding: 12, borderRadius: 12, background: "rgba(0,0,0,0.35)", overflowX: "auto", fontSize: 12 }}>
                      {JSON.stringify(decision, null, 2)}
                    </pre>
                  </details>
                </div>
              )}
            </div>
          </div>

          {/* RIGHT: Monitoring */}
          <div style={{ display: "grid", gap: 18 }}>
            <div style={card}>
              <h2 style={{ margin: 0, fontSize: 18 }}>Business Monitoring (24h)</h2>

              {!kpis ? (
                <div style={{ marginTop: 12, opacity: 0.75 }}>Loading KPIs…</div>
              ) : (
                <div style={{ marginTop: 14, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                  <div style={{ padding: 12, borderRadius: 12, background: "rgba(0,0,0,0.25)" }}>
                    <div style={label}>Total Decisions</div>
                    <div style={{ fontSize: 20, fontWeight: 900 }}>{kpis.total}</div>
                  </div>
                  <div style={{ padding: 12, borderRadius: 12, background: "rgba(0,0,0,0.25)" }}>
                    <div style={label}>Avg Risk</div>
                    <div style={{ fontSize: 20, fontWeight: 900 }}>{kpis.avg_risk.toFixed(4)}</div>
                  </div>
                  <div style={{ padding: 12, borderRadius: 12, background: "rgba(0,0,0,0.25)" }}>
                    <div style={label}>STP Rate</div>
                    <div style={{ fontSize: 20, fontWeight: 900 }}>{(kpis.stp_rate * 100).toFixed(1)}%</div>
                  </div>
                  <div style={{ padding: 12, borderRadius: 12, background: "rgba(0,0,0,0.25)" }}>
                    <div style={label}>Review Rate</div>
                    <div style={{ fontSize: 20, fontWeight: 900 }}>{(kpis.review_rate * 100).toFixed(1)}%</div>
                  </div>
                </div>
              )}

              <div style={{ marginTop: 10, opacity: 0.8, fontSize: 12 }}>
                GET {API_MONITORING}/kpis/summary
              </div>
            </div>

            <div style={card}>
              <h2 style={{ margin: 0, fontSize: 18 }}>Recent Decisions</h2>
              <div style={{ marginTop: 12, display: "grid", gap: 10 }}>
                {recent.length === 0 ? (
                  <div style={{ opacity: 0.75 }}>No recent decisions found.</div>
                ) : (
                  recent.map((d, idx) => (
                    <div
                      key={`${d.entity_id}-${idx}`}
                      style={{
                        padding: 12,
                        borderRadius: 14,
                        background: "rgba(0,0,0,0.25)",
                        border: "1px solid rgba(255,255,255,0.10)",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", gap: 10, alignItems: "center" }}>
                        <div style={{ fontWeight: 900 }}>{d.entity_id}</div>
                        <span style={actionStyle(d.action)}>{d.action}</span>
                      </div>
                      <div style={{ marginTop: 6, fontSize: 12, opacity: 0.85 }}>
                        risk: <b>{num(d.risk_signal).toFixed(4)}</b> • thr: <b>{num(d.threshold).toFixed(4)}</b> • mode:{" "}
                        <span style={badgeStyle((d.caution_mode || "GREEN") as any)}>{d.caution_mode}</span>
                      </div>
                      <div style={{ marginTop: 6, fontSize: 12, opacity: 0.80 }}>
                        reasons: {(d.reason_codes || []).join(", ") || "—"}
                      </div>
                      <div style={{ marginTop: 6, fontSize: 12, opacity: 0.75 }}>
                        rules: {(d.rule_hits || []).join(", ") || "—"}
                      </div>
                    </div>
                  ))
                )}
              </div>

              <div style={{ marginTop: 10, opacity: 0.8, fontSize: 12 }}>
                GET {API_MONITORING}/decisions/recent
              </div>
            </div>

            <div style={{ opacity: 0.75, fontSize: 12 }}>
              <b>Tip:</b> If you see CORS errors in the browser console, we’ll add CORS middleware to monitoring_service too
              (automation_api already has it).
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}