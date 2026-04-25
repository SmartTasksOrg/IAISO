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
            return f"[MAGNIFIED] {content}" # Recursive Quality Check
        return content
