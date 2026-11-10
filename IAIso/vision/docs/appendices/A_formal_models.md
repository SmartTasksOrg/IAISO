Appendix A: Formal Models

This appendix defines the mathematical foundations of the IAIso v5.0 Pressure-Control Governance model. By treating intelligence as a physical flow, we can apply control-theoretic bounds to system behavior.

1. The Core Pressure Equation

The state of an autonomous agent is represented by its internal pressure $p(t)$. The evolution of this pressure is governed by the following differential equation:

$$\frac{dp}{dt} = I(t) - D(p, t) - R(p, t)$$

Where:

$I(t)$ (Input Accumulation): The rate of intelligence growth, derived from compute intensity (FLOPs), token generation speed, and the density of active tool-calls.

$D(p, t)$ (Dissipation/Friction): Natural per-step decay plus an entropy floor on output complexity.

$R(p, t)$ (Release/Venting): A discrete function that triggers a state purge when $p(t) \ge P_{max}$.

2. Magnification & Back-Prop Logic — design concept, *not implemented*

An earlier design added a quality-gradient term, $D_{magnified} = D_{base} \cdot (1 + \beta \cdot \nabla Q)$, to the dissipation function. **This was never implemented in the reference engine.** Dissipation is passive per-step decay plus the entropy floor; there is no $\beta$ coefficient and no quality gradient $\nabla Q$.

$\nabla Q$: The gradient of quality assessment. If an output fails the Entropy Floor check, $\nabla Q$ increases, creating friction that slows the system down for refinement.

3. Threshold Dynamics

The system operates within three critical zones:

Nominal ($p < 0.70$): Autonomous execution with standard friction.

Warning ($0.70 \le p < 0.85$): Throttling of tool-calls and increased logging.

Escalation ($p \ge 0.85$): Triggering of Layer 4 escalation protocols (Multi-party human authorization).

Powered by Smarttasks — "Build with vision, count on precision."
