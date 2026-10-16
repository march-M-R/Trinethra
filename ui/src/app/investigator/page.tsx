"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { getDecisions, type DecisionRow } from "@/lib/api";
import { ErrorNotice, Icon, PageHeader } from "@/components/Workspace";
import DecisionTable from "@/components/DecisionTable";

export default function InvestigatorPage() {
  const [rows, setRows] = useState<DecisionRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [filter, setFilter] = useState("ALL");
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    let alive = true;
    getDecisions(200).then(data => { if (alive) { setRows(data); setError(false); } }).catch(() => { if (alive) setError(true); }).finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [refresh]);
  const queue = useMemo(() => rows.filter(row => row.action === "ROUTE_TO_REVIEW" || row.action === "BLOCK").sort((a, b) => Number(b.risk_signal ?? 0) - Number(a.risk_signal ?? 0)), [rows]);
  const filtered = queue.filter(row => filter === "ALL" || row.action === filter);
  return <><PageHeader eyebrow="HUMAN REVIEW" title="Review queue" description="Review flagged claims with the full picture. Cases are ordered by risk score."><Link href="/decisions" className="button secondary">All decisions <Icon name="arrow" size={15}/></Link></PageHeader>
    {error && <ErrorNotice message="The review queue is unavailable. We can’t confirm whether cases need attention." retry={() => { setLoading(true); setRefresh(v => v + 1); }}/>}
    <div className="toolbar"><div className="filter-tabs" aria-label="Filter review queue">{[{ value: "ALL", label: "All flagged" }, { value: "ROUTE_TO_REVIEW", label: "Needs review" }, { value: "BLOCK", label: "Blocked" }].map(tab => <button key={tab.value} aria-pressed={filter === tab.value} onClick={() => setFilter(tab.value)}>{tab.label}</button>)}</div><span className="queue-summary">{loading ? "Loading cases…" : `${filtered.length} cases · Highest risk first`}</span></div>
    <section className="panel"><DecisionTable rows={filtered} loading={loading} emptyTitle={error ? "Queue unavailable" : "Nothing in this view"} emptyDescription={error ? "Try again once your connection to the service is restored." : "No flagged claims match this filter among the latest 200 decisions."}/><div className="table-footer"><span>Based on the latest 200 decisions</span><span>Risk scores are signals, not findings.</span></div></section>
  </>;
}
