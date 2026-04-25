"""Performance benchmark harness for IAIso.

This harness measures throughput of the core primitives — engine.step(),
coordinator.update(), consent verification — in a tight loop, single
process. The numbers it produces are **lower bounds on a modest
container**, not production-scale figures. See README.md for the
distinction.

Usage:
    python -m iaiso.bench.microbench           # runs default suite
    python -m iaiso.bench.microbench --json    # machine-readable output

Why bother if it's not at scale?
    1. Regression detection: if step() suddenly becomes 10x slower in
       a commit, this catches it.
    2. Order-of-magnitude ceiling: if a single step takes 100 µs here,
       it cannot possibly take less than 100 µs in production.
    3. Relative comparisons: which aggregator is cheapest, what the
       audit-sink overhead looks like, etc.

What it does NOT measure:
    - Real-world network latency to Redis / SIEM endpoints.
    - Multi-process contention under load.
    - Tail latency under sustained load.
    - Memory pressure / GC pauses on long-running workloads.

For those, you need a proper load-testing rig on real hardware. That is
intentionally not part of this repository.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from typing import Callable


@dataclass
class BenchResult:
    name: str
    iterations: int
    total_seconds: float
    ops_per_second: float
    avg_microseconds: float


def timeit(name: str, fn: Callable[[int], None], iterations: int) -> BenchResult:
    start = time.perf_counter()
    fn(iterations)
    elapsed = time.perf_counter() - start
    return BenchResult(
        name=name,
        iterations=iterations,
        total_seconds=elapsed,
        ops_per_second=iterations / elapsed,
        avg_microseconds=(elapsed / iterations) * 1_000_000,
    )


# -- Benchmarks -------------------------------------------------------------


def bench_engine_step_minimal(iterations: int) -> None:
    """Plain engine.step() with no sinks, no audit, just pressure math."""
    from iaiso import PressureConfig
    from iaiso.core.engine import PressureEngine, StepInput

    cfg = PressureConfig(
        token_coefficient=0.01,
        tool_coefficient=0.1,
        dissipation_per_step=0.02,
        escalation_threshold=0.99,
        release_threshold=1.0,
    )
    eng = PressureEngine(cfg, execution_id="bench")
    step = StepInput(tokens=100, tool_calls=0)
    for _ in range(iterations):
        eng.step(step)


def bench_bounded_execution_step(iterations: int) -> None:
    """Full BoundedExecution with in-memory audit sink."""
    from iaiso import BoundedExecution, MemorySink, PressureConfig

    cfg = PressureConfig(dissipation_per_step=0.5,
                         escalation_threshold=0.99,
                         release_threshold=1.0)
    sink = MemorySink()
    with BoundedExecution.start(config=cfg, audit_sink=sink) as exec_:
        for _ in range(iterations):
            exec_.record_step(tokens=100)


def bench_coordinator_update_sum(iterations: int) -> None:
    """In-memory coordinator update with sum aggregator."""
    from iaiso.coordination import (
        CoordinatorConfig,
        SharedPressureCoordinator,
        SumAggregator,
    )

    coord = SharedPressureCoordinator(
        config=CoordinatorConfig(escalation_threshold=100.0,
                                 release_threshold=200.0),
        aggregator=SumAggregator(),
    )
    for i in range(10):
        coord.register(f"w{i}")
    worker = 0
    for _ in range(iterations):
        coord.update(f"w{worker}", 0.1 + (worker / 100))
        worker = (worker + 1) % 10


def bench_coordinator_update_max(iterations: int) -> None:
    """Max aggregator — typically faster than weighted sum."""
    from iaiso.coordination import (
        CoordinatorConfig,
        MaxAggregator,
        SharedPressureCoordinator,
    )

    coord = SharedPressureCoordinator(
        config=CoordinatorConfig(escalation_threshold=100.0,
                                 release_threshold=200.0),
        aggregator=MaxAggregator(),
    )
    for i in range(10):
        coord.register(f"w{i}")
    worker = 0
    for _ in range(iterations):
        coord.update(f"w{worker}", 0.1)
        worker = (worker + 1) % 10


def bench_consent_verify_hs256(iterations: int) -> None:
    """HS256 symmetric consent verification."""
    from iaiso import ConsentIssuer, ConsentVerifier

    secret = b"x" * 32
    issuer = ConsentIssuer(signing_key=secret, issuer="bench")
    verifier = ConsentVerifier(verification_key=secret, issuer="bench")
    token = issuer.issue(subject="u", scopes=["s"], ttl_seconds=3600).token
    for _ in range(iterations):
        verifier.verify(token)


def bench_audit_emit_null(iterations: int) -> None:
    """Null sink baseline — measures dispatch overhead."""
    from iaiso.audit import AuditEvent, NullSink

    sink = NullSink()
    event = AuditEvent(execution_id="x", kind="engine.step",
                       timestamp=0.0, data={"tokens": 100})
    for _ in range(iterations):
        sink.emit(event)


def bench_audit_emit_memory(iterations: int) -> None:
    """Memory sink — measures append overhead."""
    from iaiso.audit import AuditEvent
    from iaiso import MemorySink

    sink = MemorySink()
    event = AuditEvent(execution_id="x", kind="engine.step",
                       timestamp=0.0, data={"tokens": 100})
    for _ in range(iterations):
        sink.emit(event)


# -- Harness ----------------------------------------------------------------


DEFAULT_SUITE = [
    ("engine.step (bare)", bench_engine_step_minimal, 500_000),
    ("BoundedExecution + MemorySink", bench_bounded_execution_step, 100_000),
    ("Coordinator update (Sum, 10 workers)", bench_coordinator_update_sum, 200_000),
    ("Coordinator update (Max, 10 workers)", bench_coordinator_update_max, 200_000),
    ("Consent verify (HS256)", bench_consent_verify_hs256, 20_000),
    ("Audit emit (Null)", bench_audit_emit_null, 2_000_000),
    ("Audit emit (Memory)", bench_audit_emit_memory, 1_000_000),
]


def run_suite(
    suite: list[tuple[str, Callable[[int], None], int]],
) -> list[BenchResult]:
    results: list[BenchResult] = []
    for name, fn, iters in suite:
        print(f"[running] {name} ({iters:,} iterations)...",
              file=sys.stderr, flush=True)
        res = timeit(name, fn, iters)
        results.append(res)
        print(
            f"  {res.ops_per_second:>12,.0f} ops/s  "
            f"{res.avg_microseconds:>7.2f} µs/op",
            file=sys.stderr,
        )
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="IAIso microbenchmark")
    parser.add_argument("--json", action="store_true",
                        help="Emit results as JSON on stdout")
    parser.add_argument("--quick", action="store_true",
                        help="Run fewer iterations for a smoke test")
    args = parser.parse_args(argv)

    suite = DEFAULT_SUITE
    if args.quick:
        suite = [(n, f, max(1000, i // 50)) for (n, f, i) in suite]

    results = run_suite(suite)

    if args.json:
        print(json.dumps([asdict(r) for r in results], indent=2))
    else:
        print("\n=== Summary ===")
        for r in results:
            print(f"  {r.name:40s} {r.ops_per_second:>14,.0f} ops/s "
                  f"{r.avg_microseconds:>7.2f} µs/op")
        print(
            "\nNote: single-process Python in a container. These are\n"
            "lower bounds, not production numbers. See bench/README.md."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
