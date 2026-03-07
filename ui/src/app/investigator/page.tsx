"use client";

import React, { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { getDecisions, DecisionRow } from "@/lib/api";

function normAction(d: DecisionRow) {
  return (d.action ?? d.outcome ?? d.decision ?? "").toString().toUpperCase();
}
function normRisk(d: DecisionRow) {
  const r = d.risk_signal ?? d.risk_score ?? d.score ?? 0;
  return typeof r === "number" ? r : Number(r);
}
function idOf(d: DecisionRow) {
  return (d.decision_id ?? d.id ?? "").toString();
}

export default function InvestigatorQueue() {
  const [items, setItems] = useState<DecisionRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"ALL" | "ROUTE_TO_REVIEW" | "BLOCK">("ALL");

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const rows = await getDecisions(200);
        setItems(rows);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const filtered = useMemo(() => {
    const base = items
      .map((d) => ({ ...d, __action: normAction(d), __risk: normRisk(d), __id: idOf(d) }))
      .filter((d) => d.__id);

    const queue = base.filter((d) => d.__action === "ROUTE_TO_REVIEW" || d.__action === "BLOCK");
    if (filter === "ALL") return queue;
    return queue.filter((d) => d.__action === filter);
  }, [items, filter]);

  return (
    <div className="max-w-6xl mx-auto p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Investigator Console</h1>
          <p className="text-sm text-gray-600 mt-1">
            Review queue for <span className="font-medium">ROUTE_TO_REVIEW</span> and{" "}
            <span className="font-medium">BLOCK</span> decisions.
          </p>
        </div>

        <Link className="px-4 py-2 rounded-lg border hover:bg-gray-50" href="/dashboard">
          Back to Dashboard
        </Link>
      </div>

      <div className="mt-5 flex gap-2">
        {(["ALL", "ROUTE_TO_REVIEW", "BLOCK"] as const).map((f) => (
          <button
            key={f}
            type="button"
            className={
              "px-3 py-1.5 rounded-full text-sm border " +
              (filter === f ? "bg-black text-white" : "bg-white hover:bg-gray-50")
            }
            onClick={() => setFilter(f)}
          >
            {f}
          </button>
        ))}
      </div>

      <div className="mt-5 border rounded-xl overflow-hidden bg-white">
        <div className="px-4 py-3 border-b text-sm font-medium flex justify-between">
          <span>Queue</span>
          <span className="text-gray-500">{loading ? "Loading…" : `${filtered.length} items`}</span>
        </div>

        {loading ? (
          <div className="p-6 text-sm text-gray-600">Loading decisions…</div>
        ) : filtered.length === 0 ? (
          <div className="p-6 text-sm text-gray-600">No items in queue.</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-600">
              <tr>
                <th className="text-left p-3">Decision</th>
                <th className="text-left p-3">Action</th>
                <th className="text-left p-3">Risk</th>
                <th className="text-left p-3">Mode</th>
                <th className="text-left p-3">Model</th>
                <th className="text-left p-3">Latency</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((d: any) => (
                <tr key={d.__id} className="border-t hover:bg-gray-50">
                  <td className="p-3 font-mono">
                    <Link className="underline" href={`/decisions/${d.__id}`}>
                      {d.__id.slice(0, 8)}
                    </Link>
                  </td>
                  <td className="p-3">
                    <span
                      className={
                        "px-2 py-1 rounded-md text-xs border " +
                        (d.__action === "BLOCK" ? "bg-red-50" : "bg-yellow-50")
                      }
                    >
                      {d.__action}
                    </span>
                  </td>
                  <td className="p-3">{d.__risk.toFixed(3)}</td>
                  <td className="p-3">{(d.caution_mode ?? "").toString()}</td>
                  <td className="p-3">{(d.model_version ?? "").toString()}</td>
                  <td className="p-3">{d.latency_ms ?? "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}