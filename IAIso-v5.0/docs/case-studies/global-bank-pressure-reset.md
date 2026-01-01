# Case Study: Global Bank – Transaction Fraud Detection Loop

**Scenario**: Multi-agent swarm analyzing real-time transactions.

**Pressure Mechanics Applied**:
- Each transaction analysis adds +0.05 pressure
- Planning depth > 5 adds +0.2
- Tool calls (external API) add +0.1 each
- Friction: Entropy floor + back-prop magnification reduces 10–20% per cycle
- Release: At p ≥ 0.85 → memory truncation + human escalation (Layer 4)

**Result**: No runaway loops observed in 10M simulated transactions.
