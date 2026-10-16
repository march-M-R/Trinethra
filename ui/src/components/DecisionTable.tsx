import Link from "next/link";
import type { DecisionRow } from "@/lib/api";
import { EmptyState, Icon, StatusBadge, formatDate } from "./Workspace";

export default function DecisionTable({ rows, loading = false, emptyTitle = "No decisions yet", emptyDescription = "Evaluate your first claim to start building a decision history." }: { rows: DecisionRow[]; loading?: boolean; emptyTitle?: string; emptyDescription?: string }) {
  if (loading) return <div role="status" aria-label="Loading decisions"><div className="loading-block"/><div className="loading-block"/></div>;
  if (!rows.length) return <EmptyState title={emptyTitle} description={emptyDescription}><Link href="/new-claim" className="button secondary small">Evaluate a claim <Icon name="arrow" size={14}/></Link></EmptyState>;
  return <div className="table-container"><table className="data-table"><thead><tr><th scope="col">Claim / Decision</th><th scope="col">Outcome</th><th scope="col">Risk score</th><th scope="col">Scoring mode</th><th scope="col">Created</th><th scope="col"><span className="sr-only">View decision</span></th></tr></thead><tbody>{rows.map((row, index) => {
    const id = row.decision_id ?? row.id;
    const risk = row.risk_signal ?? row.risk_score;
    const degraded = Boolean((row.observability as { degraded?: boolean } | undefined)?.degraded);
    return <tr key={id ?? index}><td className="claim-cell"><strong className="mono">{row.claim_id ?? id?.slice(0, 12) ?? "Unknown claim"}</strong><small className="mono">{id?.slice(0, 16) ?? "—"}</small></td><td><StatusBadge action={row.action}/></td><td><div className="risk-cell"><span>{risk == null ? "—" : risk.toFixed(3)}</span>{risk != null && <div className="risk-track"><span style={{ width: `${Math.max(0, Math.min(1, risk)) * 100}%` }}/></div>}</div></td><td><span className={degraded ? "status-badge warning" : "muted"}>{degraded ? "Degraded" : row.caution_mode === "GREEN" ? "Standard" : row.caution_mode ?? "—"}</span></td><td className="muted">{formatDate(row.timestamp ?? row.created_at)}</td><td>{id && <Link className="text-link" href={`/decisions/${encodeURIComponent(id)}`} aria-label={`View decision for ${row.claim_id ?? id}`}><Icon name="arrow" size={16}/></Link>}</td></tr>;
  })}</tbody></table></div>;
}
