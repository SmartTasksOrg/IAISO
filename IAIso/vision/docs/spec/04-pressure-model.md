# Section 04: Pressure Model
`dp/dt = input_rate(t) - dissipation(p, t) - release(p, t)`

### Dissipation (Friction)
Friction is passive per-step decay plus an entropy floor. (An earlier design described a "back-propagation" feedback term; it is not implemented in the reference engine.)
