import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const maxDuration = 60;

type Context = { params: Promise<{ service: string; path: string[] }> };
const automationBase = process.env.AUTOMATION_API_BASE ?? process.env.NEXT_PUBLIC_AUTOMATION_API_BASE ?? "https://trinethra-automation-api.onrender.com";

async function handle(request: NextRequest, context: Context) {
  const { service, path } = await context.params;
  const endpoint = path.join("/");
  if (service === "explain" && request.method === "POST") {
    if (!(endpoint === "analyst" || (path.length === 2 && path[0] === "explain"))) {
      return NextResponse.json({ detail: "Unknown endpoint" }, { status: 404 });
    }
    let body;
    try { body = await request.json(); } catch { return NextResponse.json({ detail: "Invalid JSON" }, { status: 400 }); }
    if (!body || typeof body !== "object" || Array.isArray(body) || (body.payload != null && (typeof body.payload !== "object" || Array.isArray(body.payload))) || (body.decision != null && (typeof body.decision !== "object" || Array.isArray(body.decision)))) {
      return NextResponse.json({ detail: "Expected an object containing claim and decision objects" }, { status: 422 });
    }
    const payload = body.payload ?? {};
    const decision = body.decision ?? {};
    const action = String(decision.action ?? "UNKNOWN");
    const degraded = Boolean(decision.degraded || decision.observability?.degraded);
    const claimId = path[1] ?? body.claim_id;
    const factors = ["These are recorded claim facts, not measured causes of the model score."];
    for (const [key, label] of [["amount", "Claim amount"], ["previous_claims", "Previous claims"], ["days_since_policy_start", "Days since policy start"], ["police_report_filed", "Police report filed"], ["injury_involved", "Injury involved"]]) {
      if (key in payload) factors.push(`${label}: ${payload[key]}.`);
    }
    const nextSteps = action === "AUTO_APPROVE"
      ? ["Proceed with standard claim validation and settlement checks.", "Verify supporting documents before any payout."]
      : action === "BLOCK"
      ? ["Escalate the case to fraud investigation.", "Hold payout until the claim details and documents are validated."]
      : ["Route the claim to a human adjuster for manual review.", "Validate supporting documents, claim history, and incident details before settlement."];
    const risk = Number(decision.risk_signal);
    const threshold = Number(decision.threshold);
    const rationale = degraded
      ? "Scoring is degraded. The fallback score cannot authorize approval or blocking; human review is required."
      : decision.risk_signal != null && decision.threshold != null && Number.isFinite(risk) && Number.isFinite(threshold)
      ? `Risk score ${risk.toFixed(3)} is ${risk < threshold ? "below" : "at or above"} the recorded review threshold ${threshold.toFixed(3)}.`
      : "Score or threshold is unavailable, so the decision rationale cannot be verified.";
    const summary = `Recorded decision: ${action}. ${rationale} This is a template explanation of the recorded decision, not model feature attribution.`;
    if (endpoint === "analyst") {
      const question = String(body.question ?? "").trim();
      if (!question) return NextResponse.json({ detail: "Question must not be empty" }, { status: 422 });
      const checks = /next|check|document|handoff|siu/i.test(question);
      return NextResponse.json({ answer: `${summary} ${factors.join(" ")}${checks ? ` Recommended checks: ${nextSteps.join(" ")}` : ""}`, claim_id: claimId, action });
    }
    return NextResponse.json({ claim_id: claimId, summary, key_factors: factors, next_steps: nextSteps, explanation_method: "template" });
  }
  const allowed = request.method === "GET"
    ? /^(health|kpis|decisions|decisions\/[0-9a-f-]{36})$/i.test(endpoint)
    : request.method === "POST" && endpoint === "process_claim";
  if (service !== "automation" || !allowed) return NextResponse.json({ detail: "Unknown endpoint" }, { status: 404 });
  try {
    const upstream = await fetch(`${automationBase.replace(/\/$/, "")}/${endpoint}${request.nextUrl.search}`, {
      method: request.method,
      headers: { "Content-Type": "application/json" },
      body: request.method === "POST" ? await request.text() : undefined,
      cache: "no-store",
      signal: AbortSignal.timeout(55000),
      redirect: "error",
    });
    const text = await upstream.text();
    return new Response(text, { status: upstream.status, headers: { "Content-Type": upstream.headers.get("Content-Type") ?? "application/json", "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json({ detail: "The claim service is temporarily unavailable. Please try again shortly." }, { status: 502 });
  }
}
export const GET = handle;
export const POST = handle;
