"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { getDecisionById, type DecisionRow } from "@/lib/api";
import { EmptyState, ErrorNotice, Icon, PageHeader, StatusBadge, formatDate } from "@/components/Workspace";

export default function DecisionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<DecisionRow | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    let alive = true;
    getDecisionById(id).then(row => { if (alive) { setData(row); setError(false); } }).catch(() => { if (alive) setError(true); }).finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [id, refresh]);
  const observability = data?.observability as { degraded?: boolean; warning?: string; decision_summary?: string; input_limitations?: string } | undefined;
  const payload = data?.payload as Record<string, unknown> | undefined;
  return <><PageHeader eyebrow="BEHIND THE DECISION" title={data?.claim_id ?? "The claim, in context."} description="A complete record of the outcome, its reasoning, and the information considered."><Link href="/decisions" className="button secondary">Back to decisions <Icon name="arrow" size={14}/></Link></PageHeader>
    {error && <ErrorNotice message="We couldn’t retrieve this decision. Check the link or try again." retry={() => { setLoading(true); setRefresh(v => v + 1); }}/>}
    {loading ? <div className="panel" role="status" aria-label="Loading decision"><div className="loading-block"/></div> : data ? <>
      {observability?.degraded && <div role="alert" className="notice"><strong>Human review required.</strong> Scoring was degraded. {observability.warning}</div>}
      <section className="metrics-grid" aria-label="Decision summary"><div className="metric featured"><div className="metric-header">Recorded outcome<Icon name="shield" size={17}/></div><div style={{ margin: "22px 0 14px" }}><StatusBadge action={data.action}/></div><div className="metric-note">Saved to the decision record</div></div><div className="metric"><div className="metric-header">Risk score<Icon name="activity" size={17}/></div><div className="metric-value">{data.risk_signal?.toFixed(3) ?? "—"}</div><div className="metric-note">Not a confirmed fraud probability</div></div><div className="metric"><div className="metric-header">Review threshold<Icon name="clock" size={17}/></div><div className="metric-value">{data.threshold?.toFixed(3) ?? "—"}</div><div className="metric-note">Saved model operating threshold</div></div><div className="metric"><div className="metric-header">Scoring mode<Icon name="file" size={17}/></div><div className="metric-value" style={{ fontSize: 25, marginTop: 15 }}>{observability?.degraded ? "Degraded" : data.caution_mode === "GREEN" ? "Standard" : data.caution_mode ?? "—"}</div><div className="metric-note">Confidence is not calibrated</div></div></section>
      <div className="detail-grid"><section className="panel"><div className="panel-head"><h2>Decision record</h2><Icon name="file" size={17}/></div><div className="panel-body"><dl className="metadata-list">{[["Decision ID", data.decision_id ?? id], ["Claim ID", data.claim_id ?? "—"], ["Created", formatDate(data.timestamp)], ["Model version", data.model_version ?? "—"], ["Policy version", data.policy_version ?? "—"], ["Model call latency", data.latency_ms == null ? "—" : `${data.latency_ms} ms`]].map(([label, value]) => <div key={label}><dt>{label}</dt><dd className={label.includes("ID") ? "mono" : ""}>{value}</dd></div>)}</dl></div></section>
      <section className="panel"><div className="panel-head"><h2>Why this outcome?</h2><Icon name="shield" size={17}/></div><div className="panel-body">{observability?.decision_summary && <p className="muted" style={{ fontSize: 12, lineHeight: 1.9, marginBottom: 23 }}>{observability.decision_summary}</p>}<ul className="reason-list">{data.reason_codes?.length ? data.reason_codes.map(code => <li key={code}><Icon name="check" size={15}/><span>{code.toLowerCase().replaceAll("_", " ")}</span></li>) : <li>No reason codes were recorded.</li>}</ul><p className="muted" style={{ fontSize: 10, lineHeight: 1.8, marginTop: 24 }}>{observability?.input_limitations ?? "Reason codes describe the decision policy. They are not measured model feature contributions."}</p></div></section></div>
      {payload && <section className="panel" style={{ marginTop: 22 }}><div className="panel-head"><h2>Claim information</h2></div><div className="panel-body"><dl className="metadata-list">{Object.entries(payload).map(([key, value]) => <div key={key}><dt style={{ textTransform: "capitalize" }}>{key.replaceAll("_", " ")}</dt><dd>{typeof value === "boolean" ? value ? "Yes" : "No" : String(value ?? "—")}</dd></div>)}</dl></div></section>}
      <details className="panel code-details"><summary>View original decision data</summary><pre>{JSON.stringify(data, null, 2)}</pre></details>
    </> : !error && <section className="panel"><EmptyState title="Decision not found" description="This record may no longer be available. Return to the decision history to find another claim."/></section>}
  </>;
}
