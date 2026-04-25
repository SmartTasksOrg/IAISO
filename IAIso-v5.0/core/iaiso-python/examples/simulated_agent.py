"""End-to-end example: a simulated agent with pressure, consent, and audit.

This example does not call any real LLM — it simulates an agent loop so you
can run it without API keys. It demonstrates how the three core components
fit together.

Run: python examples/simulated_agent.py
"""

from __future__ import annotations

import random

from iaiso import (
    BoundedExecution,
    ConsentIssuer,
    ConsentVerifier,
    FanoutSink,
    JsonlFileSink,
    MemorySink,
    PressureConfig,
    StdoutSink,
    StepOutcome,
    generate_hs256_secret,
)


def simulated_step(step_idx: int) -> dict:
    """Simulate one agent step. Occasionally produces a 'runaway' (lots of tokens)."""
    if random.random() < 0.1 and step_idx > 3:
        return {"tokens": 5000, "tool_calls": 0, "tag": f"step_{step_idx}"}
    return {
        "tokens": random.randint(200, 800),
        "tool_calls": 1 if random.random() < 0.4 else 0,
        "tag": f"step_{step_idx}",
    }


def main() -> None:
    random.seed(42)

    # 1. Set up a consent token for the execution.
    secret = generate_hs256_secret()
    issuer = ConsentIssuer(signing_key=secret)
    verifier = ConsentVerifier(verification_key=secret)
    token = issuer.issue(
        subject="example-agent",
        scopes=["tools.search", "tools.fetch"],
        ttl_seconds=300,
    )
    scope = verifier.verify(token.token)

    # 2. Set up audit sinks: console + file + in-memory (for inspection).
    memory = MemorySink()
    sink = FanoutSink(
        StdoutSink(),
        JsonlFileSink("./example_audit.jsonl"),
        memory,
    )

    # 3. Configure the pressure engine. These coefficients are the defaults;
    #    real deployments should calibrate.
    config = PressureConfig(
        escalation_threshold=0.7,
        release_threshold=0.9,
    )

    print("\n--- Running simulated agent ---\n")

    with BoundedExecution.start(
        execution_id="example-run",
        config=config,
        consent=scope,
        audit_sink=sink,
    ) as exec_:
        for i in range(30):
            # Check before each step.
            state = exec_.check()
            if state is StepOutcome.ESCALATED:
                print(f"[step {i}] ESCALATED at pressure "
                      f"{exec_.snapshot().pressure:.3f} — pausing.")
                break
            if state is StepOutcome.LOCKED:
                print(f"[step {i}] LOCKED — reset required.")
                break

            # Require a scope before taking a 'tool' action.
            try:
                exec_.require_scope("tools.search")
            except Exception as exc:
                print(f"[step {i}] scope denied: {exc}")
                break

            # Do the work and report it.
            work = simulated_step(i)
            outcome = exec_.record_step(**work)
            print(f"[step {i}] tokens={work['tokens']:>4} "
                  f"tools={work['tool_calls']} "
                  f"pressure={exec_.snapshot().pressure:.3f} -> {outcome.value}")

    print(f"\n--- Final state ---")
    print(f"Final pressure: {exec_.snapshot().pressure:.3f}")
    print(f"Final lifecycle: {exec_.snapshot().lifecycle.value}")
    print(f"Total audit events emitted: {len(memory.events)}")
    print(f"Event kinds: {sorted(set(e.kind for e in memory.events))}")


if __name__ == "__main__":
    main()
