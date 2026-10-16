"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { processClaim, getExplanation, type ProcessClaimRequest, type ProcessClaimResponse, type ExplanationResponse } from "@/lib/api";
import { EmptyState, Icon, PageHeader, StatusBadge } from "@/components/Workspace";

const initial: ProcessClaimRequest = { claim_id: "", policy_id: "", claim_type: "AUTO", amount: 1200, zip: "", incident_date: "", days_since_policy_start: 120, age: 35, years_with_insurer: 5, previous_claims: 0, channel: "Agent", police_report_filed: false, injury_involved: false };

export default function NewClaimPage() {
  const [form, setForm] = useState(initial);
  const [decision, setDecision] = useState<ProcessClaimResponse | null>(null);
  const [explanation, setExplanation] = useState<ExplanationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  function update<K extends keyof ProcessClaimRequest>(key: K, value: ProcessClaimRequest[K]) { setForm(previous => ({ ...previous, [key]: value })); }
  async function evaluate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (loading) return;
    setLoading(true); setError(null); setDecision(null); setExplanation(null);
    try {
      const response = await processClaim(form);
      setDecision(response);
      try { setExplanation(await getExplanation(form.claim_id, form, response)); }
      catch { setError("Your decision was saved, but its explanation is unavailable. You don’t need to resubmit."); }
    } catch (e) { setError(e instanceof Error ? e.message : "We couldn’t evaluate this claim. Please try again."); }
    finally { setLoading(false); }
  }
  const risk = decision?.risk_signal ?? 0;
  return <><PageHeader eyebrow="CLAIM ASSESSMENT" title="Evaluate a claim" description="Enter the claim details for a recorded risk assessment and next steps."><Link href="/decisions" className="text-link">View decision history <Icon name="arrow" size={15}/></Link></PageHeader>
    <div className="intake-layout"><form className="panel intake-form" onSubmit={evaluate}>
      <fieldset className="form-section" disabled={loading || Boolean(decision)}><legend><span className="section-number">01</span> Claim essentials</legend><div className="field-grid">
        <label className="field"><span>Claim ID</span><input required maxLength={128} value={form.claim_id} onChange={e => update("claim_id", e.target.value)} placeholder="CLM-1001"/></label>
        <label className="field"><span>Policy ID</span><input required maxLength={128} value={form.policy_id} onChange={e => update("policy_id", e.target.value)} placeholder="POL-1234"/></label>
        <label className="field"><span>Claim type</span><input value="Auto insurance" readOnly/></label>
        <label className="field"><span>Claim amount ($)</span><input type="number" required min="0.01" step="0.01" value={form.amount} onChange={e => update("amount", Number(e.target.value))}/></label>
        <label className="field"><span>Incident date</span><input type="date" required value={form.incident_date} onChange={e => update("incident_date", e.target.value)}/></label>
        <label className="field"><span>ZIP code</span><input required inputMode="numeric" pattern="[0-9]{5}(-[0-9]{4})?" title="Enter a five-digit ZIP code, optionally followed by a four-digit extension" value={form.zip} onChange={e => update("zip", e.target.value)} placeholder="07302"/></label>
      </div></fieldset>
      <fieldset className="form-section" disabled={loading || Boolean(decision)}><legend><span className="section-number">02</span> Policyholder context</legend><div className="field-grid">
        <label className="field"><span>Policyholder age</span><input type="number" required min={16} max={120} value={form.age} onChange={e => update("age", Number(e.target.value))}/></label>
        <label className="field"><span>Previous claims</span><input type="number" required min={0} value={form.previous_claims} onChange={e => update("previous_claims", Number(e.target.value))}/></label>
        <label className="field"><span>Days since policy start</span><input type="number" required min={0} value={form.days_since_policy_start} onChange={e => update("days_since_policy_start", Number(e.target.value))}/></label>
        <label className="field"><span>Years with insurer</span><input type="number" required min={0} value={form.years_with_insurer} onChange={e => update("years_with_insurer", Number(e.target.value))}/></label>
      </div></fieldset>
      <fieldset className="form-section" disabled={loading || Boolean(decision)}><legend><span className="section-number">03</span> Supporting details</legend><div className="field-grid"><label className="field full"><span>Submission channel</span><select value={form.channel} onChange={e => update("channel", e.target.value)}>{["Agent", "Online", "Call Center", "Partner"].map(channel => <option key={channel}>{channel}</option>)}</select></label><label className="check-field"><input type="checkbox" checked={form.police_report_filed} onChange={e => update("police_report_filed", e.target.checked)}/>Police report filed</label><label className="check-field"><input type="checkbox" checked={form.injury_involved} onChange={e => update("injury_involved", e.target.checked)}/>Injury involved</label></div></fieldset>
      {error && <div role="alert" className="notice">{error}</div>}
      <div className="form-footer">{decision ? <button type="button" className="button secondary" disabled={loading} onClick={() => { setForm(initial); setDecision(null); setExplanation(null); setError(null); }}>Start another claim <Icon name="plus" size={16}/></button> : <button type="submit" className="button primary" disabled={loading}>{loading ? "Evaluating your claim…" : "Evaluate claim"}<Icon name={loading ? "activity" : "arrow"} size={16}/></button>}<p>All fields are required. Your decision is saved to the claim history.</p></div>
    </form>
    <aside className="panel result-panel" aria-live="polite" aria-busy={loading}><div className="result-label"><span>Decision workspace</span><span className="subtle-tag">{loading ? "Evaluating" : decision ? "Saved" : "Awaiting claim"}</span></div>
      {!decision ? <><EmptyState icon={loading ? "activity" : "shield"} title={loading ? "Connecting the dots…" : "Your assessment"} description={loading ? "We’re evaluating your claim and preparing its decision record." : "Complete the claim details to see the risk score, outcome, and recommended next steps."}/><div className="result-step"><Icon name="file" size={15}/> Claim details <Icon name="arrow" size={12}/> Risk score <Icon name="arrow" size={12}/> Decision</div></> : <>
        <div className="result-summary"><StatusBadge action={decision.action}/><div className="risk-number">{risk.toFixed(3)}<small>/ 1.000</small></div><span className="muted" style={{ fontSize: 11 }}>Model risk score</span><div className="risk-meter"><span style={{ width: `${Math.max(0, Math.min(1, risk)) * 100}%` }}/><i style={{ left: `${Math.max(0, Math.min(1, decision.threshold ?? 0)) * 100}%` }}/></div><div className="risk-meter-labels"><span>Lower risk</span><span>Review threshold: {decision.threshold?.toFixed(3) ?? "—"}</span></div>{decision.degraded && <div role="alert" className="notice">Scoring is degraded. Human review is required. {decision.warning}</div>}</div>
        <div className="detail-section"><h3>What this means</h3><p>{explanation?.summary ?? (loading ? "Preparing the explanation…" : "The decision is saved. An explanation is currently unavailable.")}</p></div>
        {explanation?.key_factors?.length ? <div className="detail-section"><h3>Claim facts for review</h3><ul>{explanation.key_factors.map(fact => <li key={fact}>{fact}</li>)}</ul></div> : null}
        {explanation?.next_steps?.length ? <div className="detail-section"><h3>Your next steps</h3><ul>{explanation.next_steps.map(step => <li key={step}>{step}</li>)}</ul></div> : null}
        <div className="detail-section"><p>Partial intake uses defaults for missing model attributes. Scores are not calibrated fraud probabilities; confidence is unavailable.</p>{typeof decision.decision_id === "string" && <Link href={`/decisions/${encodeURIComponent(decision.decision_id)}`} className="text-link">Open saved decision <Icon name="arrow" size={14}/></Link>}</div>
      </>}
    </aside></div>
  </>;
}
