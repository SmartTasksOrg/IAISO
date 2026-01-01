# haystack Integration Guide

Pressure-Control Wrapper active.

## Quick Start Example

```python
from haystack import Agent  # adjust import as needed
from iaiso.core import IAIsoPressureWrapper  # assuming core wrapper exists

agent = Agent(model="appropriate-model")
safe_agent = IAIsoPressureWrapper(
    agent=agent,
    pressure_threshold=0.85,
    enable_magnification=True,
    dissipation_rate=0.15
)

result = safe_agent.run("your task here")
```

Pressure monitoring, friction, and release events are automatically applied.
