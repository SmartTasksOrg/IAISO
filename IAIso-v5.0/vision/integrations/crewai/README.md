# IAIso v5.0 + CrewAI Integration
```python
from crewai import Crew
from iaiso.integrations.crewai import IAIsoCrewWrapper

crew = Crew(agents=[a1, a2], tasks=[t1, t2])

# Multi-agent coordination with Layer 3.5
safe_crew = IAIsoCrewWrapper(
    crew=crew,
    global_pressure_limit=0.8,
    enable_phase_detection=True
)

result = safe_crew.kickoff()
```
