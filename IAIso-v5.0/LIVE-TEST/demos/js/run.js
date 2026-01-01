// Node demo that calls the canonical Python server.
// No reimplementation of pressure math → no drift.
const base = process.env.IAISO_BASE_URL || "http://127.0.0.1:8787";

async function post(path, body) {
  const res = await fetch(base + path, {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify(body)
  });
  return await res.json();
}

console.log("\n=== IAIso LIVE TEST — Node.js (calls Python server) ===\n");
console.log("Base:", base);

// reset first
await post("/reset", {});

for (let i = 1; i <= 20; i++) {
  const out = await post("/step", { complexity: i });
  console.log(JSON.stringify(out, null, 2));
  if (out.status === "RELEASED") break;
}
