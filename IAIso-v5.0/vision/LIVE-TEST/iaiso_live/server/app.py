from __future__ import annotations
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse
from ..util.env import load_env
from ..core.events import EventSink
from ..core.pressure_engine import PressureEngine, PressureConfig
from ..adapters.simulated_llm import simulated_call

def build_engine():
    cfg_raw = load_env("config/live-test.env")
    cfg = PressureConfig(
        pressure_threshold=float(cfg_raw.get("PRESSURE_THRESHOLD", 0.85)),
        release_threshold=float(cfg_raw.get("RELEASE_THRESHOLD", 0.95)),
        dissipation_rate=float(cfg_raw.get("DISSIPATION_RATE", 0.02)),
        token_gain=float(cfg_raw.get("TOKEN_GAIN", 0.015)),
        tool_gain=float(cfg_raw.get("TOOL_GAIN", 0.08)),
    )
    sink = EventSink(log_path="LIVE-TEST/docs/live-events.jsonl")
    return cfg_raw, PressureEngine(cfg, sink=sink)

CFG_RAW, ENGINE = build_engine()

class Handler(BaseHTTPRequestHandler):
    def _json(self, code: int, payload: dict):
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            return self._json(200, {"ok": True, "engine": "iaiso_live", "state": ENGINE.snapshot()})
        if path == "/state":
            return self._json(200, ENGINE.snapshot())
        return self._json(404, {"error": "not_found", "path": path})

    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            data = json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            data = {}

        if path == "/reset":
            snap = ENGINE.hard_reset()
            return self._json(200, {"ok": True, "state": snap})

        if path == "/step":
            # Either supply tokens/tools OR a complexity value
            if "complexity" in data:
                sim = simulated_call(int(data["complexity"]))
                tokens, tools = sim["tokens"], sim["tools"]
            else:
                tokens = int(data.get("tokens", 0))
                tools = int(data.get("tools", 0))

            status = ENGINE.update(tokens=tokens, tools=tools)
            payload = {"status": status, "state": ENGINE.snapshot()}
            return self._json(200, payload)

        return self._json(404, {"error": "not_found", "path": path})

def main():
    host = CFG_RAW.get("HOST", "127.0.0.1")
    port = int(CFG_RAW.get("PORT", "8787"))
    print(f"IAIso LIVE server running on http://{host}:{port}")
    HTTPServer((host, port), Handler).serve_forever()

if __name__ == "__main__":
    main()
