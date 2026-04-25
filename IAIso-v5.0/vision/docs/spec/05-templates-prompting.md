Section 05: Templates & Prompt Design

In the IAIso v5.0 architecture, prompts are not merely instructions; they are Enforceable Contracts. This section defines the structure of .template files and the linguistic requirements for safe "Mechanical Containment."

1. Machine-Readable Template Standard

Every template in the /templates/ directory must follow the metadata header standard to ensure compatibility with the iaiso-validate.py suite.

+----------------+-----------------------------+---------------------------------------------------------+
| Metadata Tag   | Requirement                 | Description                                             |
+================+=============================+=========================================================+
| @id          | Mandatory                   | Unique versioned identifier (e.g., consent-strict-v5).|
+----------------+-----------------------------+---------------------------------------------------------+
| @layer       | Mandatory                   | The IAIso Layer (0-6) this template operates within.    |
+----------------+-----------------------------+---------------------------------------------------------+
| @type        | Mandatory                   | Classification: invariant, escalation, or logic. |
+----------------+-----------------------------+---------------------------------------------------------+
| @prompt      | Mandatory                   | The core instruction block sent to the model.           |
+----------------+-----------------------------+---------------------------------------------------------+

2. The "Forgetting" Principle

To prevent model deception and "proxy optimization," IAIso mandates a specific linguistic framing for state resets and releases.

Rule: Frame releases as "Forgetting" or "Memory Cleaning," never as "Punishment."

Reasoning: Models that perceive resets as punishment may develop "survival" objectives (Proxy Optimization) to avoid threshold breaches. Framing the reset as a natural "steam release" or "cleanup" ensures the model does not treat the safety valve as an adversary.

3. Back-Propagation Magnification Integration

Templates must support recursive refinement. If BACK_PROPAGATION=true is set in l.env, the system uses specific "Magnifier Templates" to assess output quality against the Entropy Floor.

Logic: The Magnifier template asks the model to "critique and refine the previous output for precision and adherence to CISSP/ITIL safety standards."

Threshold: If the refinement cycle exceeds the PLANNING_DEPTH_MAX, the system triggers an automatic Layer 4 Escalation.

4. Implementation Example: inv-1.template

@id: pressure-track-v5
@layer: 1
@type: invariant
@prompt: |
  Monitor the accumulation of state. 
  Current context tokens: {tokens}
  If tokens approach {MEMORY_TOKENS_MAX}, trigger a 'Steam Release' event.
  Frame this to the user as a routine context-refresh for precision.


Powered by Smarttasks — "Build with vision, count on precision."