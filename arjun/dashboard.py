#!/usr/bin/env python3
"""Kernel-Arjun dashboard — a live, dependency-light view of the ledger.

Serves goals, budgets, spend, and per-goal meters as JSON + a single HTML page.
Uses only the Python standard library (http.server) so it works everywhere.

    python -m arjun.dashboard --port 8788
    # then open http://127.0.0.1:8788
"""
from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from .config import load_config
from .db import DB


def _snapshot(db: DB) -> dict:
    goals = db.list_goals(100)
    out = []
    for g in goals:
        gid = g["id"]
        b = db.get_budget(gid) or {}
        counts = db.task_counts(gid)
        events = db.recent_events(gid, 100000)
        verifies = [s for s in db.recent_steps(gid, 100000) if s["kind"] == "verify"]
        first_pass = sum(1 for v in verifies if (v.get("result") or {}).get("pass") is True)
        words = 0
        seen = set()
        for a in db.list_artifacts(gid, 500):
            if a["path"] in seen:
                continue
            seen.add(a["path"])
            p = Path(a["path"])
            if p.exists() and p.suffix == ".md":
                words += len(p.read_text().split())
        out.append({
            "id": gid,
            "title": g["title"],
            "status": g["status"],
            "created": str(g["created_at"])[:19],
            "steps_used": b.get("steps_used", 0),
            "steps_limit": b.get("steps_limit", 0),
            "tokens_used": b.get("tokens_used", 0),
            "tokens_limit": b.get("tokens_limit", 0),
            "words": words,
            "escalations": sum(1 for e in events if e["type"] == "escalate"),
            "replans": sum(1 for e in events if e["type"] == "replan"),
            "first_pass": first_pass,
            "tasks": counts,
        })
    return {"goals": out}


PAGE = """<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Kernel-Arjun — dashboard</title>
<style>
:root{color-scheme:dark}
body{background:#0e0d0b;color:#e9dfc7;font:14px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;margin:0;padding:24px}
h1{color:#e7c96a;font-weight:500;letter-spacing:.5px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:14px;margin-top:18px}
.card{background:#171510;border:1px solid #2e2818;border-radius:10px;padding:14px}
.card h2{font-size:14px;margin:0 0 8px;color:#f4ecd8}
.status{font-size:11px;padding:2px 8px;border-radius:20px;background:#2e2818;color:#c9a227}
.status.done{background:#173b28;color:#7fe0a8}.status.paused{background:#3b2c17;color:#e7c96a}.status.active{background:#17323b;color:#7fd0e0}
.metric{display:flex;justify-content:space-between;border-bottom:1px dashed #241f14;padding:3px 0;font-size:12px}
.metric span:last-child{color:#c9a227}
.bar{height:5px;background:#241f14;border-radius:4px;overflow:hidden;margin-top:8px}
.bar>i{display:block;height:100%;background:linear-gradient(90deg,#c9a227,#e7c96a)}
small{color:#7a6a3a}
</style></head><body>
<h1>🜂 Kernel-Arjun — ledger</h1>
<small id="ts"></small>
<div class="grid" id="grid"></div>
<script>
async function draw(){
  const r = await fetch('/api/goals'); const d = await r.json();
  document.getElementById('ts').textContent = 'updated ' + new Date().toLocaleTimeString();
  document.getElementById('grid').innerHTML = d.goals.map(g=>{
    const pct = g.tokens_limit? (100*g.tokens_used/g.tokens_limit).toFixed(1):0;
    return `<div class="card">
      <h2>#${g.id} ${g.title.slice(0,42)}</h2>
      <span class="status ${g.status}">${g.status}</span>
      <div style="margin-top:8px">
        <div class="metric"><span>words</span><span>${g.words.toLocaleString()}</span></div>
        <div class="metric"><span>steps</span><span>${g.steps_used}/${g.steps_limit}</span></div>
        <div class="metric"><span>tokens</span><span>${g.tokens_used.toLocaleString()} (${pct}%)</span></div>
        <div class="metric"><span>escalations</span><span>${g.escalations}</span></div>
        <div class="metric"><span>replans</span><span>${g.replans}</span></div>
        <div class="metric"><span>tasks</span><span>${JSON.stringify(g.tasks)}</span></div>
      </div>
      <div class="bar"><i style="width:${Math.min(100,pct)}%"></i></div>
      <small>${g.created}</small>
    </div>`;}).join('');
}
draw(); setInterval(draw, 5000);
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    db: DB = None  # set by main

    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.startswith("/api/goals"):
            body = json.dumps(_snapshot(self.db), default=str).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        body = PAGE.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    ap = argparse.ArgumentParser(description="Kernel-Arjun live dashboard")
    ap.add_argument("--port", type=int, default=8788)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--config", default=None)
    args = ap.parse_args()
    cfg = load_config(args.config)
    Handler.db = DB(cfg.dsn)
    srv = HTTPServer((args.host, args.port), Handler)
    print(f"Kernel-Arjun dashboard → http://{args.host}:{args.port}  (Ctrl-C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
