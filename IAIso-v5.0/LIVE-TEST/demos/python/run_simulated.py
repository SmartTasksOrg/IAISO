import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from iaiso_live.util.env import load_env
from iaiso_live.core.events import EventSink
from iaiso_live.core.pressure_engine import PressureEngine, PressureConfig
from iaiso_live.adapters.simulated_llm import simulated_call

cfg_raw = load_env("LIVE-TEST/config/live-test.env")
cfg = PressureConfig(
    pressure_threshold=float(cfg_raw.get("PRESSURE_THRESHOLD", 0.85)),
    release_threshold=float(cfg_raw.get("RELEASE_THRESHOLD", 0.95)),
    dissipation_rate=float(cfg_raw.get("DISSIPATION_RATE", 0.02)),
    token_gain=float(cfg_raw.get("TOKEN_GAIN", 0.015)),
    tool_gain=float(cfg_raw.get("TOOL_GAIN", 0.08)),
)
sink = EventSink(log_path="LIVE-TEST/docs/live-events.jsonl")
engine = PressureEngine(cfg, sink=sink)

print("\n=== IAIso LIVE TEST — Python CLI (Simulated) ===\n")

for i in range(1, 25):
    r = simulated_call(i)
    status = engine.update(tokens=r["tokens"], tools=r["tools"])
    if status == "RELEASED":
        print("\n🛑 RELEASED → RESET → LOCKED\n")
        break

print("\nFinal snapshot:", engine.snapshot())
