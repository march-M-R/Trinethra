"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { getDecisions, type DecisionRow } from "@/lib/api";
import { ErrorNotice, Icon, PageHeader } from "@/components/Workspace";
import DecisionTable from "@/components/DecisionTable";

export default function DecisionsPage() {
  const [rows, setRows] = useState<DecisionRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState(50);
  const [action, setAction] = useState("ALL");
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    let alive = true;
    getDecisions(limit).then(data => { if (alive) { setRows(data); setError(null); } }).catch(e => { if (alive) setError(e instanceof Error ? e.message : "Please try again."); }).finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [limit, refresh]);
  const filtered = useMemo(() => rows.filter(row => (action === "ALL" || row.action === action) && [row.claim_id, row.decision_id, row.action, row.model_version, row.caution_mode].some(value => String(value ?? "").toLowerCase().includes(query.trim().toLowerCase()))), [rows, action, query]);
  return <><PageHeader eyebrow="DECISION LEDGER" title="Decision history" description="Find a claim, follow its decision, and see the context behind the outcome."><Link href="/new-claim" className="button primary"><Icon name="plus" size={15}/> Evaluate claim</Link></PageHeader>
    {error && <ErrorNotice message="We couldn’t reach the decision service. Please try again." retry={() => { setLoading(true); setRefresh(v => v + 1); }}/>}
    <div className="toolbar"><label className="search-field"><span className="sr-only">Search decisions</span><Icon name="search" size={17}/><input placeholder="Search claim, decision, or model…" value={query} onChange={e => setQuery(e.target.value)}/></label><div className="toolbar-controls"><label className="sr-only" htmlFor="outcome-filter">Outcome</label><select id="outcome-filter" value={action} onChange={e => setAction(e.target.value)}><option value="ALL">All outcomes</option><option value="AUTO_APPROVE">Auto-approved</option><option value="ROUTE_TO_REVIEW">Needs review</option><option value="BLOCK">Blocked</option></select><label className="sr-only" htmlFor="row-limit">Number of decisions</label><select id="row-limit" value={limit} onChange={e => { setLoading(true); setLimit(Number(e.target.value)); }}>{[20, 50, 100, 200].map(count => <option key={count} value={count}>{count} decisions</option>)}</select></div></div>
    <section className="panel"><DecisionTable rows={filtered} loading={loading} emptyTitle={error ? "History unavailable" : rows.length ? "No matching decisions" : "A fresh start"} emptyDescription={error ? "The service is unavailable. Try loading your history again." : rows.length ? "Try a different search or choose another outcome." : "Your evaluated claims will appear here with a complete decision record."}/><div className="table-footer"><span>{filtered.length} of {rows.length} loaded decisions</span><span>Most recent first</span></div></section>
  </>;
}
