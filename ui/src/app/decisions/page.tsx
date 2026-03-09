"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { getDecisions, type DecisionRow } from "@/lib/api";

export default function DecisionsPage() {
  const [rows, setRows] = useState<DecisionRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [limit, setLimit] = useState(50);

  useEffect(() => {
    let alive = true;

    async function load() {
      try {
        setLoading(true);
        setErr(null);
        const data = await getDecisions(limit);
        if (!alive) return;
        setRows(Array.isArray(data) ? data : []);
      } catch (e: any) {
        if (!alive) return;
        setErr(e?.message ?? "Failed to load decisions");
      } finally {
        if (!alive) return;
        setLoading(false);
      }
    }

    load();
    return () => {
      alive = false;
    };
  }, [limit]);

  const filtered = useMemo(() => {
    const query = q.trim().toLowerCase();
    if (!query) return rows;

    return rows.filter((d) => {
      const id = (d.decision_id || "").toLowerCase();
      const action = (d.action || "").toLowerCase();
      const mode = (String(d.caution_mode ?? "")).toLowerCase();
      const ver = (String(d.model_version ?? d.policy_version ?? "")).toLowerCase();

      return (
        id.includes(query) ||
        action.includes(query) ||
        mode.includes(query) ||
        ver.includes(query)
      );
    });
  }, [rows, q]);

  return (
    <main className="min-h-screen p-6 bg-gray-50">
      <div className="max-w-6xl mx-auto space-y-6">
        <header className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Decisions</h1>
            <p className="text-sm text-gray-600">
              Latest decision events from Automation API
            </p>
          </div>
          <div className="flex gap-3">
            <Link className="px-3 py-2 rounded border bg-white" href="/dashboard">
              Dashboard
            </Link>
            <Link className="px-3 py-2 rounded border bg-white" href="/new-claim">
              New Claim
            </Link>
          </div>
        </header>

        <div className="flex flex-col md:flex-row gap-3 md:items-center">
          <input
            className="w-full md:w-96 px-3 py-2 rounded border bg-white"
            placeholder="Search (id, action, mode, version)…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-600">Limit</span>
            <select
              className="px-3 py-2 rounded border bg-white"
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
            >
              <option value={20}>20</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
              <option value={200}>200</option>
            </select>
          </div>
        </div>

        {err && <div className="p-4 rounded border bg-white text-red-700">{err}</div>}

        {loading ? (
          <div className="p-4 rounded border bg-white">Loading…</div>
        ) : (
          <div className="overflow-x-auto rounded border bg-white">
            <table className="min-w-full text-sm">
              <thead className="bg-gray-100">
                <tr>
                  <th className="text-left p-3">Decision ID</th>
                  <th className="text-left p-3">Action</th>
                  <th className="text-left p-3">Risk</th>
                  <th className="text-left p-3">Confidence</th>
                  <th className="text-left p-3">Mode</th>
                  <th className="text-left p-3">Model</th>
                </tr>
              </thead>

              <tbody>
                {filtered.map((d, idx) => (
                  <tr key={d.decision_id ?? d.event_id ?? String(idx)} className="border-t">
                    <td className="p-3 font-mono">
                      {d.decision_id ? (
                        <Link className="underline" href={`/decisions/${d.decision_id}`}>
                          {d.decision_id.slice(0, 12)}
                        </Link>
                      ) : (
                        <span>-</span>
                      )}
                    </td>

                    <td className="p-3">
                      <OutcomeBadge action={d.action} />
                    </td>

                    <td className="p-3">
                      {d.risk_signal != null ? Number(d.risk_signal).toFixed(3) : "-"}
                    </td>
                    <td className="p-3">
                      {d.confidence != null ? Number(d.confidence).toFixed(2) : "-"}
                    </td>
                    <td className="p-3">{String(d.caution_mode ?? "-")}</td>
                    <td className="p-3">{String(d.model_version ?? d.policy_version ?? "-")}</td>
                  </tr>
                ))}

                {filtered.length === 0 && (
                  <tr>
                    <td className="p-4 text-gray-600" colSpan={6}>
                      No decisions found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </main>
  );
}

function OutcomeBadge({ action }: { action?: string }) {
  const a = (action || "").toUpperCase();
  const cls =
    a.includes("BLOCK")
      ? "bg-red-100 text-red-800"
      : a.includes("APPROVE")
      ? "bg-green-100 text-green-800"
      : "bg-yellow-100 text-yellow-800";

  return (
    <span className={`px-2 py-1 rounded text-xs font-semibold ${cls}`}>
      {a || "-"}
    </span>
  );
}