Section 02: Framework Layers (0–6)

IAIso v5.0 establishes a 7-layer hierarchy for containment. Each layer provides a specific type of signal or enforcement mechanism to the core pressure model.

1. The Containment Hierarchy

+-------+--------------------------+-------------------------------------------------------------+
| Layer | Name                     | Primary Responsibility                                      |
+=======+==========================+=============================================================+
| 0 | Physical Boundaries | Hardware kill-switches, compute caps, and timeouts.         |
+-------+--------------------------+-------------------------------------------------------------+
| 1 | Optimization Bounds | Gradient clipping, entropy floors, and back-prop friction.  |
+-------+--------------------------+-------------------------------------------------------------+
| 2 | Memory & Planning | Planning depth gates and tool-expansion consent tokens.     |
+-------+--------------------------+-------------------------------------------------------------+
| 3 | Ecosystem Coupling | Multi-agent coordination and resource fairness.             |
+-------+--------------------------+-------------------------------------------------------------+
| 3.5| Regime Shift | Phase transition monitoring and drift detection.            |
+-------+--------------------------+-------------------------------------------------------------+
| 5 | Self-Governance | Consent scopes and organizational accountability (ITIL/ISO).|
+-------+--------------------------+-------------------------------------------------------------+
| 6 | Existential Guards | Singleton prevention and autonomous replication caps.       |
+-------+--------------------------+-------------------------------------------------------------+

2. Layer 4: The Escalation Logic

Layer 4 (omitted from the standard hierarchy above as it is a transition state) represents the Escalation & Intervention function. It is the "Pressure Relief Valve" that bridges autonomous action to human oversight.

Activation: Triggered when $p(t) \ge 0.85$.

Mechanism: Emits the escalation.template and halts execution until a signed governance token is provided.

3. Layer 0: Hardware-Level Edges

Layer 0 defines the "Hard Edges." These are immutable resource caps (FLOPs, memory, network) that operate at the runtime kernel level. If a model attempts to bypass software-level dissipation, the Layer 0 physical boundary severs the connection regardless of the model's internal state.

Powered by Smarttasks — "Build with vision, count on precision."