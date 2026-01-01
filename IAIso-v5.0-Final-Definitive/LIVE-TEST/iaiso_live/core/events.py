from __future__ import annotations
import json, time
from pathlib import Path

class EventSink:
    def __init__(self, log_path: str | None = None):
        self.log_path = Path(log_path) if log_path else None
        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event: str, **data):
        payload = {"ts": time.time(), "event": event, **data}
        # pretty to stdout
        print(json.dumps(payload, indent=2, sort_keys=True))
        # jsonl to file
        if self.log_path:
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(payload, sort_keys=True) + "\n")
        return payload
