"use client";

import React, { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  AreaChart,
  Area,
} from "recharts";
import { getKpiSummary, getDecisions } from "@/lib/api";

type Kpis = {
  total_decisions: number;
  approvals: number;
  blocks: number;
  fraud_rate: number;
};

function toNum(v: any) {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

function sumKeys(obj: Record<string, any>, predicate: (k: string) => boolean) {
  return Object.entries(obj || {}).reduce((acc, [k, v]) => {
    if (!predicate(k)) return acc;
    return acc + toNum(v);
  }, 0);
}

export default function DashboardPage() {
  const [kpis, setKpis] = useState<Kpis>({
    total_decisions: 0,
    approvals: 0,
    blocks: 0,
    fraud_rate: 0,
  });

  const [recent, setRecent] = useState<any[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;

    async function load() {
      try {
        setErr(null);
        setLoading(true);

        const [k, d] = await Promise.all([getKpiSummary(24), getDecisions(20)]);
        if (!alive) return;

        const total = toNum(k?.total_decisions ?? 0);
        const byAction: Record<string, any> = k?.by_action ?? {};

        const approvals = sumKeys(byAction, (key) =>
          key.toUpperCase().includes("APPROVE")
        );

        const blocks = sumKeys(byAction, (key) =>
          key.toUpperCase().includes("BLOCK")
        );

        const fraudRate = total > 0 ? (blocks / total) * 100 : 0;

        setKpis({
          total_decisions: total,
          approvals,
          blocks,
          fraud_rate: fraudRate,
        });

        setRecent(Array.isArray(d) ? d : []);
      } catch (e: any) {
        if (!alive) return;
        setErr(e?.message ?? "Failed to load dashboard");
        setRecent([]);
        setKpis({
          total_decisions: 0,
          approvals: 0,
          blocks: 0,
          fraud_rate: 0,
        });
      } finally {
        if (!alive) return;
        setLoading(false);
      }
    }

    load();
    const t = setInterval(load, 5000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  const chartData = useMemo(() => {
    const arr = Array.isArray(recent) ? recent : [];
    return arr
      .slice(0, 12)
      .reverse()
      .map((r: any, idx: number) => ({
        name: (r.decision_id ?? r.id ?? `#${idx + 1}`).toString().slice(0, 6),
        risk: toNum(r.risk_signal ?? r.risk_score ?? r.score ?? 0),
        confidence: toNum(r.confidence ?? 0),
      }));
  }, [recent]);

  const latest = recent?.[0];
  const latestAction = (latest?.action ?? latest?.outcome ?? latest?.decision ?? "")
    .toString()
    .toUpperCase();

  return (
    <main className="min-h-screen bg-gradient-to-b from-gray-50 to-white text-gray-900">
      <div className="max-w-7xl mx-auto px-6 py-8 space-y-8">
        <header className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="inline-flex items-center rounded-full border border-gray-200 bg-white px-3 py-1 text-xs font-medium text-gray-600 shadow-sm">
              Trinetra · Insurance Risk Intelligence
            </div>
            <h1 className="mt-3 text-3xl font-bold tracking-tight">
              Decision Intelligence Dashboard
            </h1>
            <p className="mt-2 text-sm text-gray-600 max-w-2xl">
              Monitor automated claim decisions, fraud risk movement, and recent
              review activity across the platform.
            </p>
          </div>

          <div className="flex flex-wrap gap-3">
            <Link
              href="/new-claim"
              className="rounded-xl bg-black px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:opacity-90"
            >
              Evaluate New Claim
            </Link>
            <Link
              href="/decisions"
              className="rounded-xl border border-gray-300 bg-white px-4 py-2.5 text-sm font-semibold text-gray-800 hover:bg-gray-50"
            >
              View Decisions
            </Link>
          </div>
        </header>

        {err && (
          <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {err}
          </div>
        )}

        <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          <MetricCard
            title="Total Decisions"
            value={kpis.total_decisions}
            subtitle="Last 24 hours"
          />
          <MetricCard
            title="Approvals"
            value={kpis.approvals}
            subtitle="Auto-approved cases"
          />
          <MetricCard
            title="Blocks"
            value={kpis.blocks}
            subtitle="High-risk prevented"
          />
          <MetricCard
            title="Fraud Rate"
            value={`${kpis.fraud_rate.toFixed(2)}%`}
            subtitle="Block share of total"
          />
        </section>

        <section className="grid grid-cols-1 gap-6 xl:grid-cols-3">
          <div className="xl:col-span-2 rounded-3xl border border-gray-200 bg-white p-6 shadow-sm">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold">Risk Signal Trend</h2>
                <p className="text-sm text-gray-500">
                  Recent decision risk trajectory across processed claims
                </p>
              </div>
              <div className="rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-600">
                Auto-refresh · 5s
              </div>
            </div>

            <div className="mt-6 h-[320px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData}>
                  <defs>
                    <linearGradient id="riskFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopOpacity={0.25} />
                      <stop offset="95%" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="name" />
                  <YAxis domain={[0, 1]} />
                  <Tooltip />
                  <Area
                    type="monotone"
                    dataKey="risk"
                    strokeWidth={2}
                    fillOpacity={1}
                    fill="url(#riskFill)"
                  />
                  <Line type="monotone" dataKey="risk" dot={false} strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="rounded-3xl border border-gray-200 bg-white p-6 shadow-sm">
            <h2 className="text-lg font-semibold">Latest Decision Snapshot</h2>
            <p className="mt-1 text-sm text-gray-500">
              Most recent decision captured by the platform
            </p>

            {latest ? (
              <div className="mt-5 space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-500">Decision ID</span>
                  <span className="font-mono text-sm text-gray-800">
                    {String(latest.decision_id ?? latest.id ?? "-").slice(0, 12)}
                  </span>
                </div>

                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-500">Action</span>
                  <OutcomeBadge action={latestAction} />
                </div>

                <div className="grid grid-cols-2 gap-3 pt-2">
                  <MiniStat
                    label="Risk"
                    value={toNum(
                      latest?.risk_signal ?? latest?.risk_score ?? latest?.score ?? 0
                    ).toFixed(3)}
                  />
                  <MiniStat
                    label="Confidence"
                    value={toNum(latest?.confidence ?? 0).toFixed(2)}
                  />
                  <MiniStat
                    label="Mode"
                    value={String(latest?.caution_mode ?? latest?.mode ?? "-")}
                  />
                  <MiniStat
                    label="Latency"
                    value={`${toNum(latest?.latency_ms ?? 0)} ms`}
                  />
                </div>

                <Link
                  href={`/decisions/${encodeURIComponent(
                    String(latest?.decision_id ?? latest?.id ?? "")
                  )}`}
                  className="mt-2 inline-flex rounded-xl border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-800 hover:bg-gray-50"
                >
                  Open Decision
                </Link>
              </div>
            ) : (
              <div className="mt-6 rounded-2xl border border-dashed border-gray-300 bg-gray-50 p-6 text-sm text-gray-500">
                No decisions yet.
              </div>
            )}
          </div>
        </section>

        <section className="rounded-3xl border border-gray-200 bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold">Recent Decisions</h2>
              <p className="text-sm text-gray-500">
                Latest outcomes from the automation pipeline
              </p>
            </div>
            {loading && (
              <span className="text-xs font-medium text-gray-500">Refreshing…</span>
            )}
          </div>

          <div className="mt-5 overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-left text-gray-500">
                  <th className="pb-3 font-medium">Decision ID</th>
                  <th className="pb-3 font-medium">Action</th>
                  <th className="pb-3 font-medium">Risk</th>
                  <th className="pb-3 font-medium">Confidence</th>
                  <th className="pb-3 font-medium">Mode</th>
                  <th className="pb-3 font-medium">Model</th>
                </tr>
              </thead>
              <tbody>
                {(Array.isArray(recent) ? recent : []).slice(0, 8).map((r: any) => {
                  const id = (r.decision_id ?? r.id ?? "").toString();
                  const action = (r.action ?? r.outcome ?? r.decision ?? "")
                    .toString()
                    .toUpperCase();
                  const risk = toNum(r.risk_signal ?? r.risk_score ?? r.score ?? 0);
                  const conf = toNum(r.confidence ?? 0);
                  const mode = (r.caution_mode ?? r.mode ?? "").toString();
                  const model = (r.model_version ?? r.model ?? "-").toString();

                  return (
                    <tr key={id} className="border-b border-gray-100 last:border-0">
                      <td className="py-4 pr-4">
                        <Link
                          href={id ? `/decisions/${encodeURIComponent(id)}` : "/decisions"}
                          className="font-mono text-gray-800 hover:underline"
                        >
                          {id.slice(0, 12) || "—"}
                        </Link>
                      </td>
                      <td className="py-4 pr-4">
                        <OutcomeBadge action={action} />
                      </td>
                      <td className="py-4 pr-4">{risk.toFixed(3)}</td>
                      <td className="py-4 pr-4">{conf.toFixed(2)}</td>
                      <td className="py-4 pr-4">{mode || "-"}</td>
                      <td className="py-4 pr-4">{model}</td>
                    </tr>
                  );
                })}

                {(!recent || recent.length === 0) && (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-sm text-gray-500">
                      No decisions yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </main>
  );
}

function MetricCard({
  title,
  value,
  subtitle,
}: {
  title: string;
  value: string | number;
  subtitle: string;
}) {
  return (
    <div className="rounded-3xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="text-sm font-medium text-gray-500">{title}</div>
      <div className="mt-2 text-3xl font-bold tracking-tight">{value}</div>
      <div className="mt-2 text-xs text-gray-500">{subtitle}</div>
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-gray-50 p-3">
      <div className="text-xs text-gray-500">{label}</div>
      <div className="mt-1 text-sm font-semibold text-gray-900">{value}</div>
    </div>
  );
}

function OutcomeBadge({ action }: { action: string }) {
  const a = (action || "").toUpperCase();
  const cls =
    a.includes("BLOCK")
      ? "bg-red-100 text-red-800 border-red-200"
      : a.includes("APPROVE")
      ? "bg-green-100 text-green-800 border-green-200"
      : "bg-yellow-100 text-yellow-800 border-yellow-200";

  return (
    <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${cls}`}>
      {a || "-"}
    </span>
  );
}