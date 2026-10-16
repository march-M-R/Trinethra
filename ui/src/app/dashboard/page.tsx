"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getDecisions, getKpiSummary, type DecisionRow, type KpiSummary } from "@/lib/api";
import { EmptyState, ErrorNotice, Icon, PageHeader } from "@/components/Workspace";
import DecisionTable from "@/components/DecisionTable";

export default function DashboardPage() {
  const [kpis, setKpis] = useState<KpiSummary | null>(null);
  const [recent, setRecent] = useState<DecisionRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [windowHours, setWindowHours] = useState(24);
  const [refresh, setRefresh] = useState(0);

  const retry = useCallback(() => setRefresh(value => value + 1), []);
  useEffect(() => {
    let alive = true;
    let pending = false;
    async function load() {
      if (pending) return;
      pending = true;
      try {
        const [summary, decisions] = await Promise.all([getKpiSummary(windowHours), getDecisions(20)]);
        if (alive) { setKpis(summary); setRecent(decisions); setError(null); }
      } catch (e) { if (alive) setError(e instanceof Error ? e.message : "Please check your connection and try again."); }
      finally { pending = false; if (alive) setLoading(false); }
    }
    load();
    const interval = setInterval(load, 15000);
    return () => { alive = false; clearInterval(interval); };
  }, [windowHours, refresh]);

  const total = kpis?.total_decisions ?? kpis?.total ?? 0;
  const approvals = kpis?.approvals ?? kpis?.by_action?.AUTO_APPROVE ?? 0;
  const reviews = kpis?.reviews ?? kpis?.by_action?.ROUTE_TO_REVIEW ?? 0;
  const blocks = kpis?.blocks ?? kpis?.by_action?.BLOCK ?? 0;
  const distribution = [
    { name: "Auto-approved", value: approvals, color: "#718c7f" },
    { name: "Needs review", value: reviews, color: "#b6a074" },
    { name: "Blocked", value: blocks, color: "#ae8980" },
  ];
  const chartData = [...recent].reverse().map((row, index) => ({ name: String(index + 1).padStart(2, "0"), risk: row.risk_signal ?? row.risk_score ?? null, claim: row.claim_id ?? "Claim" }));
  const metricValue = (value: number, suffix = "") => loading || !kpis ? "—" : value.toLocaleString(undefined, { maximumFractionDigits: suffix ? 1 : 0 }) + suffix;
  return <>
    <PageHeader eyebrow="CLAIMS INTELLIGENCE" title="Portfolio overview" description="A considered view of your claims, decisions, and review activity.">
      <label className="sr-only" htmlFor="time-window">Reporting period</label><select id="time-window" style={{ width: "auto", fontSize: 11 }} value={windowHours} onChange={e => { setLoading(true); setWindowHours(Number(e.target.value)); }}><option value={24}>Last 24 hours</option><option value={168}>Last 7 days</option><option value={720}>Last 30 days</option></select>
      <Link className="button primary" href="/new-claim"><Icon name="plus" size={15}/> Evaluate claim</Link>
    </PageHeader>
    {error && <ErrorNotice message={kpis ? "The latest refresh failed. Previously loaded data is shown." : "Your services may be starting up. No live data is available yet."} retry={retry}/>}
    <section className="metrics-grid" aria-label="Portfolio metrics">
      {[{ label: "Claims processed", value: metricValue(total), icon: "file", note: "In the selected period", cls: "featured" }, { label: "Auto-approved", value: metricValue(approvals), icon: "check", note: "Eligible for standard checks", cls: "" }, { label: "Needs review", value: metricValue(reviews), icon: "clock", note: "Routed to human review", cls: "warning" }, { label: "Block rate", value: metricValue(total ? blocks / total * 100 : 0, "%"), icon: "shield", note: "Share of decisions blocked", cls: "" }].map(metric => <article className={`metric ${metric.cls}`} key={metric.label}><div className="metric-header">{metric.label}<span className="metric-icon"><Icon name={metric.icon} size={16}/></span></div><div className="metric-value">{metric.value}</div><div className="metric-note"><span/>{metric.note}</div></article>)}
    </section>
    <section className="dashboard-middle">
      <article className="panel"><div className="panel-head"><div><h2>Risk overview</h2><p>Risk scores across the latest processed claims</p></div><span className="subtle-tag"><Icon name="activity" size={12}/> Latest 20 decisions</span></div>
        {loading ? <div className="loading-block" style={{ height: 190 }}/> : recent.length ? <div className="chart-wrap"><ResponsiveContainer width="100%" height="100%"><AreaChart data={chartData} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}><defs><linearGradient id="riskGradient" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#b6a074" stopOpacity={.25}/><stop offset="100%" stopColor="#b6a074" stopOpacity={.01}/></linearGradient></defs><CartesianGrid stroke="#e2e5da" strokeDasharray="3 5" vertical={false}/><XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: "#8d9c80", fontSize: 9 }} dy={10}/><YAxis domain={[0, 1]} axisLine={false} tickLine={false} tick={{ fill: "#8d9c80", fontSize: 9 }} ticks={[0, .25, .5, .75, 1]}/><Tooltip contentStyle={{ background: "#fffef9", color: "#5d7451", border: "1px solid #dce3cf", borderRadius: 8, fontSize: 11 }} formatter={value => [Number(value).toFixed(3), "Risk score"]} labelFormatter={(_, payload) => payload[0]?.payload?.claim ?? "Claim"}/><Area type="monotone" dataKey="risk" stroke="#8b9e7d" strokeWidth={2} fill="url(#riskGradient)" connectNulls={false} activeDot={{ r: 4, fill: "#7b946a", stroke: "white", strokeWidth: 2 }}/></AreaChart></ResponsiveContainer></div> : <div className="empty-chart"><EmptyState icon="activity" title={error ? "Risk data is unavailable" : "Your risk picture starts here"} description="Claim scores will appear as you evaluate claims. No sample data is shown."/></div>}
        <div className="chart-foot"><span className="chart-legend">Model risk score · 0 to 1</span><span>Refreshes every 15 seconds</span></div>
      </article>
      <article className="panel"><div className="panel-head"><div><h2>Decision outcomes</h2><p>Decision mix in the selected period</p></div></div><div className="panel-body" style={{ paddingBottom: 12 }}><div className="distribution-total"><strong>{loading || !kpis ? "—" : total.toLocaleString()}</strong><span>total decisions</span></div><div className="distribution-bar" aria-label="Decision distribution">{distribution.map(item => <span key={item.name} style={{ width: `${total ? item.value / total * 100 : 0}%`, background: item.color }}/>)}</div>{distribution.map(item => <div className="distribution-row" key={item.name}><span><i className="legend-square" style={{ background: item.color }}/>{item.name}</span><strong>{kpis ? item.value : "—"}<small>{kpis ? `${total ? (item.value / total * 100).toFixed(0) : 0}%` : ""}</small></strong></div>)}</div><Link className="review-callout" href="/investigator"><span>Give complex claims a closer look.</span><Icon name="arrow" size={16}/></Link></article>
    </section>
    <section className="panel"><div className="panel-head" style={{ paddingBottom: 21 }}><div><h2>Recent decisions</h2><p>A traceable record of each claim and its outcome</p></div><Link className="text-link" href="/decisions">View all <Icon name="arrow" size={14}/></Link></div><DecisionTable rows={recent.slice(0, 5)} loading={loading} emptyTitle={error ? "Decision history is unavailable" : "Ready for your first claim?"} emptyDescription={error ? "Reconnect to the service to view recorded decisions." : "Evaluate a claim to see its outcome and risk score here."}/><div className="table-footer"><span>Latest {Math.min(recent.length, 5)} decisions · All time</span><span>Scores support review; they do not confirm fraud.</span></div></section>
  </>;
}
