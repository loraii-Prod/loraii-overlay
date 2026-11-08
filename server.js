// OverDrive Wildcard 2026: bracket overlay + live sync server.
// Serves index.html and a tiny state API so every OBS source, dock and browser shows the same bracket.
//   GET  /api/state?since=<rev>  -> 200 {state} when newer, 204 when unchanged
//   POST /api/state               -> apply a patch {matches?, opts?, air?, cast?, autoSync?, wsTimer?} (needs X-Sync-Key)
//   POST /api/sheet               -> pull the Google Sheet now (needs X-Sync-Key)
// The server also pulls the sheet every 30 s (when autoSync is on) and runs Auto switch between parts.
const http = require("http");
const fs = require("fs");
const path = require("path");

const PORT = process.env.PORT || 10000;
const KEY = process.env.SYNC_KEY || "";
const SHEET_CSV = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQD2Um71alwYDoejxYV15ud9NZLq8E0re8efnSUDkw5M-HN_ApEd9KOmVhuiwEm0bzPdmdQbeHw0NgC/pub?gid=0&single=true&output=csv";
const INDEX = fs.readFileSync(path.join(__dirname, "index.html"));

let state = { matches: {}, opts: {}, air: 1, cast: null, wsTimer: null, autoSync: true, rev: 0, sheetAt: null };
let lastRotate = Date.now();
const bump = () => { state.rev = Date.now(); };

function applyPatch(p) {
  if (!p || typeof p !== "object") return;
  if (p.matches && typeof p.matches === "object") {
    for (const [id, m] of Object.entries(p.matches)) {
      if (!/^R\d_(UB|LB)\d$/.test(id) || typeof m !== "object") continue;
      const cur = state.matches[id] || {};
      for (const k of ["s1", "s2", "time", "at", "live"]) if (k in m) cur[k] = m[k];
      state.matches[id] = cur;
    }
  }
  if (p.opts && typeof p.opts === "object") Object.assign(state.opts, p.opts);
  if (p.air === 1 || p.air === 2) { state.air = p.air; lastRotate = Date.now(); }
  if ("cast" in p) state.cast = p.cast && /^R\d_(UB|LB)\d$/.test(p.cast) ? p.cast : null;
  if ("autoSync" in p) state.autoSync = !!p.autoSync;
  if ("wsTimer" in p) state.wsTimer = typeof p.wsTimer === "number" && p.wsTimer > 0 ? p.wsTimer : null;
  bump();
}

function parseCSV(text) {
  const rows = []; let row = [], f = "", q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) { if (c === '"') { if (text[i + 1] === '"') { f += '"'; i++; } else q = false; } else f += c; }
    else if (c === '"') q = true; else if (c === ",") { row.push(f); f = ""; }
    else if (c === "\n" || c === "\r") { if (c === "\r" && text[i + 1] === "\n") i++; row.push(f); rows.push(row); row = []; f = ""; }
    else f += c;
  }
  if (f || row.length) { row.push(f); rows.push(row); }
  return rows;
}
const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
async function pullSheet() {
  const res = await fetch(SHEET_CSV + "&_t=" + Date.now());
  if (!res.ok) throw new Error("HTTP " + res.status);
  const rows = parseCSV(await res.text()).slice(1);
  const patch = {};
  for (const r of rows) {
    const mid = (r[30] || "").trim(), bid = (r[31] || "").trim();
    if (!mid.startsWith("M_") || !/^R\d_(UB|LB)\d$/.test(bid)) continue;
    const m = { s1: (r[43] || "").trim().toUpperCase(), s2: (r[44] || "").trim().toUpperCase() };
    const status = (r[39] || "").trim();
    if (/live|ongoing|in.?progress|playing/i.test(status)) m.live = true; else if (/completed/i.test(status)) m.live = false;
    const t = /^(\d{1,2})\/(\d{1,2})\/(\d{4})\s+(\d{1,2}):(\d{2})/.exec((r[34] || "").trim());
    if (t) {
      const d = new Date(+t[3], +t[1] - 1, +t[2]);
      m.time = DAYS[d.getDay()] + " " + t[4].padStart(2, "0") + ":" + t[5];
      m.at = `${t[3]}-${t[1].padStart(2, "0")}-${t[2].padStart(2, "0")}T${t[4].padStart(2, "0")}:${t[5]}`;
    }
    patch[bid] = m;
  }
  // only bump the revision when something actually changed
  const before = JSON.stringify(state.matches);
  for (const [id, m] of Object.entries(patch)) state.matches[id] = Object.assign(state.matches[id] || {}, m);
  state.sheetAt = new Date().toISOString();
  if (JSON.stringify(state.matches) !== before) bump();
  return Object.keys(patch).length;
}
setInterval(() => { if (state.autoSync) pullSheet().catch(e => console.log("sheet:", e.message)); }, 30000);
pullSheet().catch(e => console.log("sheet:", e.message));

// Auto switch between Part 1 and Part 2, run here so every source flips together
setInterval(() => {
  const o = state.opts || {};
  if (o.rotate && Date.now() - lastRotate >= Math.max(5, +o.rotateSec || 20) * 1000) {
    state.air = state.air === 1 ? 2 : 1; lastRotate = Date.now(); bump();
  }
}, 500);

function send(res, code, body, type) {
  res.writeHead(code, { "Content-Type": type || "application/json", "Cache-Control": "no-store", "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type, X-Sync-Key" });
  res.end(body);
}
function authorised(req) { return KEY && req.headers["x-sync-key"] === KEY; }

http.createServer((req, res) => {
  const url = new URL(req.url, "http://x");
  if (req.method === "OPTIONS") return send(res, 204, "");
  if (url.pathname === "/api/state" && req.method === "GET") {
    const since = +url.searchParams.get("since") || 0;
    if (since && since === state.rev) return send(res, 204, "");
    return send(res, 200, JSON.stringify(state));
  }
  if ((url.pathname === "/api/state" || url.pathname === "/api/sheet") && req.method === "POST") {
    if (!authorised(req)) return send(res, 403, JSON.stringify({ error: "Wrong or missing sync key" }));
    let body = "";
    req.on("data", c => { body += c; if (body.length > 200000) req.destroy(); });
    req.on("end", async () => {
      if (url.pathname === "/api/sheet") {
        try { const n = await pullSheet(); return send(res, 200, JSON.stringify({ pulled: n, rev: state.rev })); }
        catch (e) { return send(res, 502, JSON.stringify({ error: e.message })); }
      }
      try { applyPatch(JSON.parse(body || "{}")); } catch (e) { return send(res, 400, JSON.stringify({ error: "Bad JSON" })); }
      send(res, 200, JSON.stringify({ rev: state.rev }));
    });
    return;
  }
  if (url.pathname === "/healthz") return send(res, 200, "ok", "text/plain");
  if (url.pathname === "/" || url.pathname === "/index.html") return send(res, 200, INDEX, "text/html; charset=utf-8");
  send(res, 404, "Not found", "text/plain");
}).listen(PORT, () => console.log("OverDrive bracket sync on", PORT, KEY ? "(writes need key)" : "(no SYNC_KEY set: writes disabled)"));
