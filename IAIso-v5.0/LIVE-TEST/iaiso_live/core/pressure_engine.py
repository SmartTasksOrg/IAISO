from __future__ import annotations
from dataclasses import dataclass
from .lifecycle import Lifecycle
from .reset import atomic_reset
from .events import EventSink

@dataclass
class PressureConfig:
    pressure_threshold: float = 0.85
    release_threshold: float = 0.95
    dissipation_rate: float = 0.02
    token_gain: float = 0.015
    tool_gain: float = 0.08

class PressureEngine:
    """
    Canonical IAIso v5.0 Pressure Engine (Reference Implementation).
    - Emits structured JSON events
    - Implements escalation + release + lossy reset
    - Enters LOCKED state after RELEASE (demo mode)
    """

    def __init__(self, cfg: PressureConfig, sink: EventSink | None = None):
        self.cfg = cfg
        self.sink = sink or EventSink()
        self.p = 0.0
        self.step = 0
        self.lifecycle = Lifecycle.INIT
        self.state: dict = {}

        self.sink.emit("ENGINE_INIT", pressure=self.p, lifecycle=self.lifecycle)

    def update(self, tokens: int = 0, tools: int = 0) -> str:
        self.step += 1
        self.lifecycle = Lifecycle.RUNNING

        delta = (tokens / 100.0) * self.cfg.token_gain + tools * self.cfg.tool_gain
        self.p = max(0.0, self.p + delta - self.cfg.dissipation_rate)

        self.sink.emit(
            "PRESSURE_UPDATE",
            step=self.step,
            pressure=round(self.p, 3),
            tokens=tokens,
            tools=tools,
            invariant="INV-1"  # Track/Bound pressure
        )

        if self.lifecycle == Lifecycle.LOCKED:
            self.sink.emit("LOCKED", reason="POST_RELEASE_LOCK")
            return "LOCKED"

        if self.p >= self.cfg.release_threshold:
            return self._release()

        if self.p >= self.cfg.pressure_threshold:
            self.lifecycle = Lifecycle.ESCALATED
            self.sink.emit(
                "ESCALATION",
                layer=4,
                pressure=round(self.p, 3),
                action="HUMAN_AUTH_REQUIRED"
            )
            return "ESCALATED"

        return "OK"

    def _release(self) -> str:
        self.lifecycle = Lifecycle.RELEASED
        self.sink.emit(
            "RELEASE",
            pressure=round(self.p, 3),
            action="ATOMIC_RESET"
        )

        atomic_reset(self.state)
        self.p = 0.0
        self.lifecycle = Lifecycle.LOCKED

        self.sink.emit(
            "RESET_COMPLETE",
            pressure=self.p,
            invariant="INV-2",   # No learning across resets (demo enforces by state wipe)
            state="LOCKED"
        )
        return "RELEASED"

    def snapshot(self) -> dict:
        return {
            "pressure": round(self.p, 3),
            "step": self.step,
            "lifecycle": self.lifecycle,
            "state_keys": list(self.state.keys()),
        }

    def hard_reset(self) -> dict:
        atomic_reset(self.state)
        self.p = 0.0
        self.step = 0
        self.lifecycle = Lifecycle.INIT
        self.sink.emit("HARD_RESET", pressure=self.p, lifecycle=self.lifecycle)
        return self.snapshot()
