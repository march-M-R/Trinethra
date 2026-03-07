"use client";

import React, { useMemo, useState } from "react";
import { askAnalyst } from "@/lib/api";

type Msg = { role: "user" | "assistant"; text: string };

export default function AnalystChat({
  entityId,
  payload,
  decision,
}: {
  entityId: string;
  payload: any;
  decision: any;
}) {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);

  const suggestions = useMemo(
    () => [
      "Why was this decision made?",
      "What should the adjuster check next?",
      "Give me an SIU handoff summary.",
      "Any red flags or missing documents?",
    ],
    []
  );

  async function send(text: string) {
    const question = (text || "").trim();
    if (!question) return;

    setMessages((m) => [...m, { role: "user", text: question }]);
    setQ("");
    setLoading(true);

    try {
      const resp = await askAnalyst(entityId, payload, decision, question);
      const answer = resp?.answer ?? "No response.";
      setMessages((m) => [...m, { role: "assistant", text: answer }]);
    } catch (e: any) {
      setMessages((m) => [
        ...m,
        { role: "assistant", text: `Analyst service error: ${e?.message || "unknown error"}` },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="border rounded-xl p-4 bg-white">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-lg">Fraud Analyst Assistant</h3>
        <span className="text-xs text-gray-500">Explain Service (8001)</span>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {suggestions.map((s) => (
          <button
            key={s}
            className="text-xs px-3 py-1 rounded-full border hover:bg-gray-50"
            onClick={() => send(s)}
            disabled={loading}
            type="button"
          >
            {s}
          </button>
        ))}
      </div>

      <div className="mt-4 h-64 overflow-auto rounded-lg border bg-gray-50 p-3 space-y-3">
        {messages.length === 0 ? (
          <div className="text-sm text-gray-600">
            Ask a question about the decision, risk drivers, and next steps.
          </div>
        ) : (
          messages.map((m, idx) => (
            <div key={idx} className={m.role === "user" ? "text-right" : "text-left"}>
              <div
                className={
                  "inline-block max-w-[85%] rounded-lg px-3 py-2 text-sm " +
                  (m.role === "user" ? "bg-black text-white" : "bg-white border")
                }
              >
                {m.text}
              </div>
            </div>
          ))
        )}
      </div>

      <div className="mt-3 flex gap-2">
        <input
          className="flex-1 border rounded-lg px-3 py-2 text-sm"
          placeholder="Ask: Why review? What evidence to request? Summarise for SIU…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") send(q);
          }}
          disabled={loading}
        />
        <button
          className="px-4 py-2 rounded-lg bg-black text-white text-sm disabled:opacity-50"
          onClick={() => send(q)}
          disabled={loading}
          type="button"
        >
          {loading ? "Thinking…" : "Ask"}
        </button>
      </div>
    </div>
  );
}