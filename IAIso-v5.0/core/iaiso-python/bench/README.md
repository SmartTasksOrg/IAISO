# IAIso Microbenchmark

## What this measures

`iaiso.bench.microbench` runs each primitive in a tight single-process
Python loop on a container-grade CPU. The numbers it produces are
**lower bounds on throughput** — nothing can be faster than the
primitive itself, so any real deployment will be slower than these
numbers, not faster.

## Sample results

Results from running on the container used during development. Your
numbers will vary; benchmarks should be run on target hardware.

| Primitive | Throughput | Per-op cost |
|---|---|---|
| `engine.step` (bare) | ~260,000 ops/s | ~3.8 µs |
| `BoundedExecution + MemorySink` | ~170,000 ops/s | ~5.9 µs |
| `SharedPressureCoordinator.update` (Sum, 10 workers) | ~300,000 ops/s | ~3.3 µs |
| `SharedPressureCoordinator.update` (Max, 10 workers) | ~270,000 ops/s | ~3.7 µs |
| `ConsentVerifier.verify` (HS256) | ~31,000 ops/s | ~32 µs |
| Audit dispatch (NullSink) | ~15.5M ops/s | ~0.06 µs |
| Audit dispatch (MemorySink) | ~9.3M ops/s | ~0.11 µs |

## What these numbers do and don't mean

**Do**:
- Show that the pressure engine is not the bottleneck in any realistic
  agent loop. An agent making an LLM call every ~1 second would see
  IAIso's overhead as microseconds of a request that takes seconds.
- Catch performance regressions. A 10x slowdown in these numbers is
  always a bug.
- Provide an upper bound on per-process throughput. If you need to push
  >100,000 executions/second through a single process, that's
  theoretically possible; beyond that you need multiple processes.

**Don't**:
- Predict throughput under real load. Real agents talk to LLMs, Redis,
  and SIEMs. Those are orders of magnitude slower than the primitives
  measured here.
- Describe tail latency. The numbers here are averages; p99 under GC
  pressure is a different question these micro-benchmarks can't answer.
- Scale linearly. 10x the executions does not mean 1/10 the per-op
  cost; lock contention, memory pressure, and context switches change
  the shape.

## What you should do before depending on these numbers

1. Run the benchmark on your production hardware. Container vs bare
   metal vs cloud-VM numbers differ substantially.
2. Run a real load test against a small cluster — 100 concurrent agents
   using IAIso with your real LLM provider and your real SIEM — and
   measure what breaks first. It probably isn't IAIso.
3. If you're specifically worried about the coordinator being a
   bottleneck in a large fleet, use the Redis-backed coordinator
   (`iaiso.coordination.redis`) and load-test that separately.

## Consent verification is the slow one

~32 µs per HS256 verification is far slower than the other primitives.
That's because it includes HMAC-SHA256 and JSON parsing. If you're
verifying a token on every request in a hot path, cache the verified
`ConsentScope` object for its lifetime. For RS256 the cost is roughly
3-5x higher (asymmetric operations), so caching matters even more.
