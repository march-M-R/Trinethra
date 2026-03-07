"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { getDecisionById } from "@/lib/api";

export default function DecisionDetailPage() {
  const params = useParams();
  const id = String(params?.id ?? "");

  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;

    async function load() {
      if (!id) {
        if (alive) {
          setErr("Missing decision id.");
          setLoading(false);
        }
        return;
      }

      try {
        setLoading(true);
        setErr(null);

        const d = await getDecisionById(id);

        if (!alive) return;
        setData(d ?? null);
      } catch (e: any) {
        if (!alive) return;
        setErr(e?.message ?? "Failed to load decision.");
        setData(null);
      } finally {
        if (!alive) return;
        setLoading(false);
      }
    }

    load();

    return () => {
      alive = false;
    };
  }, [id]);

  const pretty = useMemo(() => {
    if (!data) return null;

    return {
      decisionId: data.decision_id ?? data.id ?? id,
      action: (data.action ?? data.outcome ?? data.decision ?? "-")
        .toString()
        .toUpperCase(),
      risk: Number(data.risk_signal ?? data.risk_score ?? data.score ?? 0),
      confidence: Number(data.confidence ?? 0),
      mode: (data.caution_mode ?? data.mode ?? "-").toString(),
      modelVersion: (data.model_version ?? data.model ?? "-").toString(),
      latencyMs: Number(data.latency_ms ?? 0),
      reasonCodes: data.reason_codes ?? [],
      timestamp: data.timestamp ?? data.event_time ?? data.created_at ?? "-",
    };
  }, [data, id]);

  return (
    <main className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        <header className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Decision Detail</h1>
            <p className="mt-2 text-sm text-gray-600">
              Detailed record for an automated insurance claim decision
            </p>
          </div>

          <div className="flex gap-3">
            <Link
              href="/dashboard"
              className="rounded-xl border border-gray-300 bg-white px-4 py-2.5 text-sm font-semibold text-gray-800 hover:bg-gray-50"
            >
              Dashboard
            </Link>
            <Link
              href="/decisions"
              className="rounded-xl border border-gray-300 bg-white px-4 py-2.5 text-sm font-semibold text-gray-800 hover:bg-gray-50"
            >
              Back to Decisions
            </Link>
          </div>
        </header>

        <div className="rounded-3xl border border-gray-200 bg-white p-6 shadow-sm">
          <div className="text-sm text-gray-500">Decision ID</div>
          <div className="mt-1 font-mono text-base text-gray-900">
            {id || "-"}
          </div>
        </div>

        {loading && (
          <div className="rounded-3xl border border-gray-200 bg-white p-6 shadow-sm text-gray-600">
            Loading decision details…
          </div>
        )}

        {err && !loading && (
          <div className="rounded-3xl border border-red-200 bg-red-50 p-6 text-red-700 shadow-sm">
            {err}
          </div>
        )}

        {!loading && !err && pretty && (
          <>
            <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
              <StatCard title="Action" value={pretty.action} />
              <StatCard title="Risk Signal" value={pretty.risk.toFixed(3)} />
              <StatCard title="Confidence" value={pretty.confidence.toFixed(2)} />
              <StatCard title="Mode" value={pretty.mode} />
            </section>

            <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <div className="rounded-3xl border border-gray-200 bg-white p-6 shadow-sm">
                <h2 className="text-lg font-semibold">Decision Metadata</h2>
                <div className="mt-4 space-y-3 text-sm">
                  <Row label="Decision ID" value={String(pretty.decisionId)} mono />
                  <Row label="Model Version" value={pretty.modelVersion} />
                  <Row label="Latency" value={`${pretty.latencyMs} ms`} />
                  <Row label="Timestamp" value={String(pretty.timestamp)} />
                </div>
              </div>

              <div className="rounded-3xl border border-gray-200 bg-white p-6 shadow-sm">
                <h2 className="text-lg font-semibold">Reason Codes</h2>
                {Array.isArray(pretty.reasonCodes) && pretty.reasonCodes.length > 0 ? (
                  <ul className="mt-4 list-disc pl-5 text-sm space-y-2 text-gray-800">
                    {pretty.reasonCodes.map((code: string, idx: number) => (
                      <li key={idx} className="font-mono">
                        {code}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div className="mt-4 text-sm text-gray-500">
                    No reason codes available.
                  </div>
                )}
              </div>
            </section>

            <section className="rounded-3xl border border-gray-200 bg-white p-6 shadow-sm">
              <h2 className="text-lg font-semibold">Raw Decision Record</h2>
              <pre className="mt-4 overflow-auto rounded-2xl bg-gray-50 p-4 text-xs text-gray-800">
                {JSON.stringify(data, null, 2)}
              </pre>
            </section>
          </>
        )}
      </div>
    </main>
  );
}

function StatCard({ title, value }: { title: string; value: string }) {
  return (
    <div className="rounded-3xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="text-sm font-medium text-gray-500">{title}</div>
      <div className="mt-2 text-2xl font-bold tracking-tight">{value}</div>
    </div>
  );
}

function Row({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-gray-100 pb-3 last:border-0 last:pb-0">
      <div className="text-gray-500">{label}</div>
      <div className={mono ? "font-mono text-right" : "text-right"}>{value}</div>
    </div>
  );
}