"use client";

import { useState } from "react";
import Link from "next/link";
import { processClaim, getExplanation } from "@/lib/api";

export default function NewClaimPage() {
  const [claimId, setClaimId] = useState("CLM-1001");
  const [policyId, setPolicyId] = useState("POL-1234");

  const [amount, setAmount] = useState(1200);
  const [zip, setZip] = useState("07302");

  const [incidentDate, setIncidentDate] = useState("2024-01-05");
  const [daysSincePolicyStart, setDaysSincePolicyStart] = useState(120);

  const [age, setAge] = useState(35);
  const [yearsWithInsurer, setYearsWithInsurer] = useState(5);
  const [previousClaims, setPreviousClaims] = useState(2);

  const [channel, setChannel] = useState("Agent");

  const [policeReport, setPoliceReport] = useState(false);
  const [injury, setInjury] = useState(false);

  const [decision, setDecision] = useState<any>(null);
  const [explanation, setExplanation] = useState<any>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onEvaluate() {
    try {
      setLoading(true);
      setError(null);
      setDecision(null);
      setExplanation(null);

      const requestBody = {
        claim_id: claimId,
        policy_id: policyId,
        claim_type: "AUTO",
        amount: Number(amount),
        zip,
        incident_date: incidentDate,
        days_since_policy_start: Number(daysSincePolicyStart),
        age: Number(age),
        years_with_insurer: Number(yearsWithInsurer),
        previous_claims: Number(previousClaims),
        channel,
        police_report_filed: policeReport,
        injury_involved: injury,
      };

      const decisionResponse = await processClaim(requestBody);
      setDecision(decisionResponse);

      const explanationResponse = await getExplanation(claimId, requestBody, {
        action: decisionResponse.action,
        risk_signal: decisionResponse.risk_signal,
        confidence: decisionResponse.confidence,
        reason_codes: decisionResponse.reason_codes,
        model_version: decisionResponse.model_version,
        policy_version: decisionResponse.policy_version,
        caution_mode: decisionResponse.caution_mode,
      });

      setExplanation(explanationResponse);
    } catch (e: any) {
      setError(e?.message ?? "Failed to evaluate claim");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        <header className="flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold">New Claim</h1>
            <p className="text-sm text-gray-600">
              Auto claim intake → model risk → decision → enriched explanation
            </p>
          </div>

          <div className="flex gap-3">
            <Link className="px-3 py-2 rounded border bg-white" href="/dashboard">
              Dashboard
            </Link>
            <Link className="px-3 py-2 rounded border bg-white" href="/decisions">
              Decisions
            </Link>
          </div>
        </header>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          
          {/* LEFT PANEL */}
          <div className="border rounded bg-white p-6 space-y-4">
            <h3 className="font-semibold text-lg">Auto Claim Intake Form</h3>

            <div>
              <label className="text-sm">Claim ID</label>
              <input
                className="w-full border rounded p-2"
                value={claimId}
                onChange={(e) => setClaimId(e.target.value)}
              />
            </div>

            <div>
              <label className="text-sm">Policy ID</label>
              <input
                className="w-full border rounded p-2"
                value={policyId}
                onChange={(e) => setPolicyId(e.target.value)}
              />
            </div>

            <div>
              <label className="text-sm">Claim Type</label>
              <input
                className="w-full border rounded p-2 bg-gray-100"
                value="AUTO"
                readOnly
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-sm">Amount ($)</label>
                <input
                  type="number"
                  className="w-full border rounded p-2"
                  value={amount}
                  onChange={(e) => setAmount(Number(e.target.value))}
                />
              </div>

              <div>
                <label className="text-sm">ZIP</label>
                <input
                  className="w-full border rounded p-2"
                  value={zip}
                  onChange={(e) => setZip(e.target.value)}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-sm">Incident Date</label>
                <input
                  type="date"
                  className="w-full border rounded p-2"
                  value={incidentDate}
                  onChange={(e) => setIncidentDate(e.target.value)}
                />
              </div>

              <div>
                <label className="text-sm">Days since policy start</label>
                <input
                  type="number"
                  className="w-full border rounded p-2"
                  value={daysSincePolicyStart}
                  onChange={(e) =>
                    setDaysSincePolicyStart(Number(e.target.value))
                  }
                />
              </div>
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="text-sm">Age</label>
                <input
                  type="number"
                  className="w-full border rounded p-2"
                  value={age}
                  onChange={(e) => setAge(Number(e.target.value))}
                />
              </div>

              <div>
                <label className="text-sm">Years with insurer</label>
                <input
                  type="number"
                  className="w-full border rounded p-2"
                  value={yearsWithInsurer}
                  onChange={(e) =>
                    setYearsWithInsurer(Number(e.target.value))
                  }
                />
              </div>

              <div>
                <label className="text-sm">Previous claims</label>
                <input
                  type="number"
                  className="w-full border rounded p-2"
                  value={previousClaims}
                  onChange={(e) =>
                    setPreviousClaims(Number(e.target.value))
                  }
                />
              </div>
            </div>

            <div>
              <label className="text-sm">Channel</label>
              <select
                className="w-full border rounded p-2"
                value={channel}
                onChange={(e) => setChannel(e.target.value)}
              >
                <option>Agent</option>
                <option>Online</option>
                <option>Call Center</option>
                <option>Partner</option>
              </select>
            </div>

            <div className="flex gap-6">
              <label className="flex gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={policeReport}
                  onChange={(e) => setPoliceReport(e.target.checked)}
                />
                Police report filed
              </label>

              <label className="flex gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={injury}
                  onChange={(e) => setInjury(e.target.checked)}
                />
                Injury involved
              </label>
            </div>

            <button
              onClick={onEvaluate}
              className="w-full bg-black text-white py-3 rounded font-semibold"
            >
              {loading ? "Evaluating..." : "Evaluate Claim"}
            </button>

            {error && (
              <div className="border border-red-500 text-red-700 p-3 rounded">
                {error}
              </div>
            )}
          </div>

          {/* RIGHT PANEL */}
          <div className="border rounded bg-white p-6 space-y-4">
            <h3 className="font-semibold text-lg">Decision Result</h3>

            {!decision && (
              <p className="text-gray-600">
                Fill the form and click Evaluate Claim.
              </p>
            )}

            {decision && (
              <>
                <div className="border rounded p-4 space-y-2">
                  <div className="font-semibold text-lg">{decision.action}</div>
                  <div>Risk signal: {decision.risk_signal}</div>
                  <div>Confidence: {decision.confidence}</div>
                  <div>Model version: {decision.model_version}</div>
                  <div>Latency: {decision.latency_ms} ms</div>
                </div>

                <div>
                  <h4 className="font-semibold">Reason Codes</h4>
                  <pre className="bg-gray-100 p-3 rounded text-sm">
                    {JSON.stringify(decision.reason_codes, null, 2)}
                  </pre>
                </div>

                <div>
                  <h4 className="font-semibold">LLM Summary</h4>
                  <div className="border rounded p-3 bg-gray-50">
                    {explanation?.summary ?? "No explanation generated."}
                  </div>
                </div>

                {Array.isArray(explanation?.key_factors) &&
                  explanation.key_factors.length > 0 && (
                    <div>
                      <h4 className="font-semibold">Key Factors</h4>
                      <ul className="list-disc pl-5 text-sm space-y-1">
                        {explanation.key_factors.map(
                          (item: string, idx: number) => (
                            <li key={idx}>{item}</li>
                          )
                        )}
                      </ul>
                    </div>
                  )}

                {Array.isArray(explanation?.next_steps) &&
                  explanation.next_steps.length > 0 && (
                    <div>
                      <h4 className="font-semibold">
                        Recommended Next Steps
                      </h4>
                      <ul className="list-disc pl-5 text-sm space-y-1">
                        {explanation.next_steps.map(
                          (item: string, idx: number) => (
                            <li key={idx}>{item}</li>
                          )
                        )}
                      </ul>
                    </div>
                  )}
              </>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}