"""
DESIGN REFERENCE — NOT SHIPPING CODE.

This lives in the `vision/` zone and is a minimal illustrative engine, not the
installable IAIso SDK (`core/iaiso-python`). `back_prop` / `magnify` document an
early design concept that the real engine does not implement (the flags are
no-ops there). Do not import this for production use.
"""
import os

class IAIsoEngine:
    def __init__(self, system_id="global-core"):
        self.p = 0.0
        self.back_prop = os.getenv("BACK_PROPAGATION", "true").lower() == "true"

    def update_pressure(self, tokens=0, tools=0):
        # dp/dt = Input - Dissipation
        delta = (tokens * 0.00015) + (tools * 0.08)
        self.p = max(0.0, self.p + delta - 0.02)
        if self.p >= 0.95:
            self.p = 0.0 # Atomic State Purge
            return "RELEASED"
        return "ESCALATED" if self.p >= 0.85 else "OK"

    def magnify(self, content):
        if self.back_prop:
            return f"[MAGNIFIED] {content}"  # DESIGN SKETCH: marker only, no refinement
        return content
