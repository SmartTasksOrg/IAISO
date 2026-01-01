#!/usr/bin/env python3
import sympy as sp
import matplotlib.pyplot as plt
import numpy as np

t = sp.symbols('t')
p = sp.Function('p')(t)

# dp/dt = input_rate - dissipation - release(p)
eq = sp.Eq(p.diff(t), 0.3 - 0.15*p - sp.Piecewise((0.5*p, p > 0.85), (0, True)))

print("Pressure Model Equation:")
sp.pprint(eq)

# Numerical simulation
from scipy.integrate import odeint

def model(p, t):
    input_rate = 0.3
    dissipation = 0.15 * p
    release = 0.5 * p if p > 0.85 else 0
    return input_rate - dissipation - release

t_span = np.linspace(0, 50, 500)
p0 = 0.0
sol = odeint(model, p0, t_span)

plt.plot(t_span, sol[:,0])
plt.axhline(0.85, color='red', linestyle='--', label='Threshold')
plt.title('IAIso Pressure Accumulation Simulation')
plt.xlabel('Time Steps')
plt.ylabel('Pressure')
plt.legend()
plt.grid(True)
plt.savefig('scripts/pressure_simulation.png')
plt.show()
