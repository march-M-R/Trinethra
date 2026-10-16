import assert from "node:assert/strict";
const base = (process.argv[2] ?? "http://127.0.0.1:3100").replace(/\/$/, "");
for (const path of ["/", "/dashboard", "/new-claim", "/decisions", "/investigator", "/brand/trinetra-transparent.png"]) {
  const response = await fetch(base + path);
  assert.equal(response.status, 200, path);
  if (path === "/") assert.ok((await response.text()).includes("The third eye"));
  console.log("PASS", path);
}
const body = { payload: { amount: 1200, previous_claims: 1 }, decision: { action: "ROUTE_TO_REVIEW", risk_signal: .2, threshold: .163 } };
const post = (path, body) => fetch(base + path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
let response = await post("/api/explain/explain/SMOKE", body);
assert.equal(response.status, 200);
const explanation = await response.json();
assert.ok(explanation.summary.includes("0.163"));
assert.equal(explanation.explanation_method, "template");
console.log("PASS explanation");
response = await post("/api/explain/analyst", { ...body, question: "What should I check next?" });
assert.equal(response.status, 200);
assert.ok((await response.json()).answer.includes("Recommended checks"));
console.log("PASS analyst");
response = await post("/api/explain/explain/SMOKE", null);
assert.equal(response.status, 422);
console.log("PASS invalid input");
response = await fetch(base + "/api/automation/arbitrary");
assert.equal(response.status, 404);
console.log("PASS proxy endpoint restriction");
