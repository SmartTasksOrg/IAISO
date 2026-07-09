# iaiso-go

**Go reference SDK for the IAIso bounded-agent-execution framework.**

IAIso adds pressure-based rate limiting, scope-based authorization, and
structured audit logging to LLM agent loops. This package is the Go
implementation of the framework's runtime layer, conformant to **IAIso
spec 1.1**.

> **Framework 5.0 · SDK 0.2.0 · status: beta.**
> Passes all **72 spec conformance vectors**, exercised by **59 test
> functions** (the vector suite runs under `go test` too),
> verified by `go test ./...` and `go run ./cmd/iaiso-conformance ./spec`.
> Emits identical event streams and produces interoperable consent tokens
> with the [Python](../iaiso-python/) and [Node](../iaiso-node/) SDKs;
> `tests/interop_test.go` proves it against the shared conformance key
> rather than asserting it.
>
> **Read [`../../LIMITATIONS.md`](../../LIMITATIONS.md) before putting this
> in an enforcement path.** IAIso bounds a *cooperating* agent. An agent
> that runs arbitrary code in this same process can disable any check in
> this package.

## Install

The module is **not published to a registry yet**. `go get
github.com/iaiso/iaiso-go` will not resolve. Depend on it from a checkout:

```bash
# in your go.mod
require github.com/iaiso/iaiso-go v0.2.0
replace github.com/iaiso/iaiso-go => ../path/to/core/iaiso-go
```

Requires Go **≥ 1.22**.

Three direct dependencies: `github.com/golang-jwt/jwt/v5` (consent
tokens, HS256 + RS256), `github.com/goccy/go-yaml` (YAML policy files),
and `github.com/redis/go-redis/v9` (the Redis coordinator). The Redis
coordinator also accepts any client satisfying the structural
`coordination.RedisClient` interface, so you are not forced onto
`go-redis` if you already have a client.

## Quick start

```go
package main

import (
    "fmt"

    "github.com/iaiso/iaiso-go/iaiso/audit"
    "github.com/iaiso/iaiso-go/iaiso/core"
)

func main() {
    sink := audit.NewMemorySink()
    err := core.Run(core.BoundedExecutionOptions{
        AuditSink: sink,
    }, func(exec *core.BoundedExecution) error {
        outcome, err := exec.RecordToolCall("search", 500)
        if err != nil {
            return err // ErrLocked once the execution is locked
        }
        if outcome == core.OutcomeEscalated {
            // Layer 4: request human review. ESCALATED does not stop
            // execution — it is a signal. Only LOCKED refuses steps.
        }
        return nil
    })
    if err != nil {
        fmt.Println("execution ended:", err)
    }
    fmt.Printf("%d audit events\n", sink.Len())
}
```

`Run` closes the execution for you. Use `core.Start` when you need to own
the lifecycle, and call `Close(errored bool)` yourself.

## Pressure engine

One scalar rises with tokens, tool calls, and planning depth, and decays
over time:

```
delta    = (tokens/1000)*tokenCoefficient + toolCalls*toolCoefficient + depth*depthCoefficient
decay    = dissipationPerStep + elapsed*dissipationPerSecond
pressure = clamp(pressure + delta - decay, 0, 1)
```

The release check runs **before** the escalation check. On release the
engine wipes pressure, and — with `PostReleaseLock` (the default) — moves
to `LOCKED`, where every further step is rejected without mutating state
until a human calls `Reset()`.

```go
cfg := core.DefaultConfig()   // esc 0.85, rel 0.95, post_release_lock true
cfg.EscalationThreshold = 0.6
engine, err := core.NewPressureEngine(cfg, core.EngineOptions{ExecutionID: "run-1"})
```

`NewPressureEngine` returns an `error` rather than panicking. Engine state
is guarded by a mutex that is **released before audit events are emitted**,
so a sink that reads back from the engine cannot deadlock it.

## Enforcement mode

`permissive` (the default) logs a warning and proceeds. `strict` refuses
to construct the engine, naming the failing condition:

```go
_, err := core.NewPressureEngine(cfg, core.EngineOptions{
    EnforcementMode:     core.EnforcementStrict,
    AuditSink:           mySink,
    CalibrationArtifact: "calibration/2026-07-01.json",
})
```

Strict mode fails closed on: a `NullSink`-only audit path (escalations
would be unobservable), `post_release_lock=false` (a released execution
resumes immediately), uncalibrated default coefficients with no
calibration artifact, and an auto-generated HS256 consent key (nothing
else could verify what it signs).

Route the permissive-mode warnings wherever you like:

```go
core.WarnLogger = log.New(os.Stderr, "iaiso ", log.LstdFlags)
```

## Consent tokens

Signed, scoped, expiring JWTs. HS256 and RS256 are both first-class.

```go
issuer, _ := consent.NewIssuer(consent.IssuerOptions{
    SigningKey: key, Algorithm: consent.RS256,
})
scope, _ := issuer.Issue(consent.IssueParams{
    Subject: "user-42", Scopes: []string{"tools.search"},
    ExecutionID: "run-1", TTLSeconds: 3600,
})

verifier, _ := consent.NewVerifier(consent.VerifierOptions{
    VerificationKey: publicKeyPEM, Algorithm: consent.RS256,
})
granted, err := verifier.RequireScope(scope.Token, "run-1", "tools.search.web")
```

Grants match on segment boundaries: `tools` grants `tools.search`, but not
`toolsbar`. Verification takes an injected `Clock`, so expiry is
deterministic in tests. Under HS256 the verifier holds the signing secret
and can forge tokens — prefer RS256 whenever the verifier is not the
issuer.

## Policy files

```go
p, err := policy.Load("policy.yaml")   // .json, .yaml, .yml
```

Validation reports the offending JSON path (`$.pressure.release_threshold:
must exceed escalation_threshold`). Unknown keys are ignored, so a policy
written for a newer IAIso still loads. Numeric *strings* are a type error,
not a coercion: `token_coefficient: "0.015"` is a typo in a
safety-critical file, and silently accepting it would hide the typo.

Policy is **trusted input**. An operator who sets `token_coefficient: 0`
has disabled the framework, and IAIso will not stop them.

## Distributed coordination

A per-agent cap does not bound a fleet: a hundred agents can each spend
just under it. The coordinator aggregates pressure across workers.

```go
c, _ := coordination.NewRedisCoordinator(ctx, coordination.RedisCoordinatorOptions{
    Redis:         coordination.FromGoRedis(rdb),
    CoordinatorID: "prod",
    Aggregator:    policy.SumAggregator{},
})
snap, _ := c.Update(ctx, "worker-1", engine.Pressure())
```

`Update` runs `HSET` + `HGETALL` inside one Lua script, so no client
observes the hash mid-write. The script source and the keyspace
(`iaiso:coord:{id}:pressures`) are byte-identical across ports — a Go
worker and a Python worker share the same namespace and the same
`EVALSHA` cache entry.

Callbacks fire on the process that observed the transition; they are not
exactly-once across the fleet. For fan-out, subscribe to the audit stream.

## Audit sinks

```go
audit.NewNullSink()                    // strict mode rejects this
audit.NewMemorySink()                  // tests
audit.NewStdoutSink()
audit.NewJSONLFileSink("audit.jsonl")  // durable; no drops
audit.NewWebhookSink(audit.WebhookOptions{URL: "..."})
audit.NewFanoutSink(a, b, c)           // one panicking sink cannot starve its siblings
```

`WebhookSink` uses a bounded queue and **drops under backpressure** rather
than stalling the agent. Alert on `Dropped()`. For regulated workloads use
`JSONLFileSink` plus a log shipper.

Every event is the same envelope: `{schema_version, execution_id, kind,
timestamp, data}`.

## Cost governance

Configure prices and the engine reports spend. Pressure remains the safety
control; spend is the readout.

```go
cfg.ModelCosts = map[string]float64{"frontier": 15.0}  // USD per 1M tokens
cfg.BudgetUSD  = 25.0
outcome := engine.Step(core.StepInput{Tokens: 50_000, Model: "frontier", Tag: &tag})
```

`spend_usd` appears on `engine.step` **only** when `ModelCosts` is set, so
existing consumers of the frozen 1.0 envelope never see a new key.
Exceeding `BudgetUSD` reuses the existing lock path — it emits
`engine.locked{reason:"budget_exceeded"}` and introduces no new lifecycle
state.

```bash
iaiso audit spend audit.jsonl --group-by tag
```

## Admin CLI

```bash
go run ./cmd/iaiso --help

iaiso policy validate policy.yaml
iaiso policy template > policy.json
IAISO_HS256_SECRET=… iaiso consent issue user-42 tools.search 3600
IAISO_HS256_SECRET=… iaiso consent verify <token>
iaiso audit tail audit.jsonl 20
iaiso audit stats audit.jsonl
iaiso audit spend audit.jsonl --group-by execution_id
iaiso coordinator demo
```

## Conformance

```bash
go run ./cmd/iaiso-conformance ./spec
# [PASS] pressure: 20/20
# [PASS] consent: 23/23
# [PASS] events: 7/7
# [PASS] policy: 22/22
#
# conformance: 72/72 vectors passed
```

The same 72 vectors also run under `go test ./tests/`, so a regression
fails CI rather than waiting for someone to run the binary.

### Float tolerance

Vector files carry a `tolerance` (1e-9). The runner uses it. Comparing
IEEE-754 doubles with `==` would fail vectors that are arithmetically
correct.

### Cross-language parity

`tests/interop_test.go` issues an HS256 token with the shared conformance
key and verifies it, and verifies the `valid_tokens` vectors minted by the
Python reference implementation. If the ports stop interoperating, this
test says so.

## Not implemented in this port

The Python SDK ships surfaces this port does not. They are absent, not
stubbed — nothing here pretends to work:

| Surface | Status |
|---|---|
| LLM provider middleware (Anthropic, OpenAI, Gemini, Bedrock, Mistral, Cohere, LiteLLM) | Not implemented |
| SIEM sinks (Splunk, Datadog, Loki, Elastic, Sumo, New Relic) | Not implemented — use `WebhookSink` or `JSONLFileSink` |
| OIDC identity verifier | Not implemented |
| Prometheus metrics sink | Not implemented — `Dropped()` and `Errors()` are exported for scraping |
| OpenTelemetry tracing sink | Not implemented |

The pressure engine, consent tokens, audit envelope, policy loader,
coordinator, conformance runner, and admin CLI — everything the 72 vectors
cover — are complete.

## Project layout

```
iaiso-go/
├── go.mod
├── go.sum
├── README.md
├── LICENSE
├── spec/                              # normative spec + conformance vectors
├── cmd/
│   ├── iaiso/                         # admin CLI entry
│   └── iaiso-conformance/             # conformance suite entry
├── tests/
│   └── interop_test.go                # cross-port parity + all 72 vectors
└── iaiso/
    ├── core/                          # engine, BoundedExecution, boot guard, cost
    ├── consent/                       # JWT issuer/verifier, scopes, revocation
    ├── audit/                         # event envelope + sinks
    ├── policy/                        # policy loader (JSON + YAML) + aggregators
    ├── coordination/                  # in-memory + Redis coordinator
    ├── conformance/                   # vector runner
    └── cli/                           # admin CLI implementation
```

## Development

```bash
go build ./...                     # compile all packages
go vet ./...                       # clean
go test ./...                      # 59 test funcs, incl. the 72-vector suite
go run ./cmd/iaiso-conformance ./spec
```

## Versioning

- Module version tracks SDK features; this is **v0.2.0**, matching the
  Python SDK.
- **Spec version** is `1.1`, defined in `./spec/VERSION`. 1.1 added
  `enforcement_mode` and five policy vectors (67 → 72). A MINOR spec bump
  never breaks existing vectors; a MAJOR spec bump ships a migration guide.
- Breaking changes in the public API are signaled by a MAJOR module bump.
- The wire-format strings (`init`, `running`, `escalated`, `released`,
  `locked`; `ok`, `escalated`, `released`, `locked`) are frozen. They are
  not Go identifiers to be prettified — they are the contract.

## License

Apache-2.0. See [LICENSE](LICENSE).

## Links

- Main repository: https://github.com/SmartTasksOrg/IAISO
- **Limitations and threat model: [`../../LIMITATIONS.md`](../../LIMITATIONS.md)**
- Framework specification: `../../vision/README.md` in the repo
- Python reference SDK: `../iaiso-python/README.md` in the repo
- Node reference SDK: `../iaiso-node/README.md` in the repo
- Conformance porting guide: `../docs/CONFORMANCE.md` in the repo
