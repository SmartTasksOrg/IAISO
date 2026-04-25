# iaiso-go

**Go reference SDK for the IAIso bounded-agent-execution framework.**

IAIso adds pressure-based rate limiting, scope-based authorization, and
structured audit logging to LLM agent loops. This package is the Go
implementation of the framework's runtime layer, conformant to **IAIso
spec 1.0**.

> Targets the normative specification shipped in [`./spec/`](./spec/).
> Passes all 67 spec conformance vectors plus 48 unit tests. Built
> alongside the [Python](../iaiso-python/) and [Node](../iaiso-node/)
> reference SDKs; all three implementations produce identical event
> streams and consent tokens for identical inputs.

## Install

```bash
go get github.com/iaiso/iaiso-go
```

Requires Go **≥ 1.22**.

This SDK uses only two transitive dependencies — `github.com/golang-jwt/jwt/v5`
for consent tokens and `github.com/goccy/go-yaml` for YAML policy
loading — so it has a small import graph. LLM provider clients,
Prometheus, OpenTelemetry, and Redis libraries are all integrated via
**structural interfaces**, so you can use the SDK with any compatible
client without taking IAIso-side dependencies on those libraries.

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
            return err
        }
        if outcome == core.StepOutcomeEscalated {
            fmt.Println("agent escalated; request human review")
        }
        return nil
    })
    if err != nil {
        fmt.Println("execution error:", err)
    }
    for _, ev := range sink.Events() {
        fmt.Printf("event: %s\n", ev.Kind)
    }
}
```

## LLM middleware

The middleware packages wrap LLM provider clients so every call is
accounted for in a `BoundedExecution`. Tokens come from the response's
usage field; tool calls come from response content blocks. If the
execution is locked or escalated (with raise-on-escalation enabled),
calls fail fast before reaching the provider.

Provider packages live under `iaiso/middleware/<provider>/`:

```go
import (
    "github.com/iaiso/iaiso-go/iaiso/middleware/anthropic"
    "github.com/iaiso/iaiso-go/iaiso/middleware/openai"
    "github.com/iaiso/iaiso-go/iaiso/middleware/gemini"
    "github.com/iaiso/iaiso-go/iaiso/middleware/bedrock"
    "github.com/iaiso/iaiso-go/iaiso/middleware/mistral"
    "github.com/iaiso/iaiso-go/iaiso/middleware/cohere"
    "github.com/iaiso/iaiso-go/iaiso/middleware/litellm"
)
```

Each provider exposes a structural `Client` interface. The pattern:

```go
// Adapter that satisfies anthropic.Client over the official Anthropic SDK.
type myAdapter struct {
    raw *officialAnthropicSDK.Client
}

func (a *myAdapter) MessagesCreate(ctx context.Context, params anthropic.MessagesCreateParams) (*anthropic.Response, error) {
    out, err := a.raw.Messages.Create(ctx, params)
    if err != nil {
        return nil, err
    }
    // Map the official response into our structural shape.
    return &anthropic.Response{
        Model:   out.Model,
        Usage:   anthropic.Usage{InputTokens: out.Usage.InputTokens, OutputTokens: out.Usage.OutputTokens},
        Content: convertContent(out.Content),
    }, nil
}

// Then wrap the adapter:
client := anthropic.New(&myAdapter{raw: rawSDK}, exec, anthropic.Options{})
resp, _ := client.MessagesCreate(ctx, params)
```

The adapter pattern keeps the SDK free of any specific provider library —
plug in whichever Go LLM library you already use.

## Distributed coordination

```go
import "github.com/iaiso/iaiso-go/iaiso/coordination"
```

In-memory coordinator:

```go
c, _ := coordination.NewSharedPressureCoordinator(coordination.CoordinatorOptions{
    EscalationThreshold: 5.0,
    ReleaseThreshold:    8.0,
    Callbacks: coordination.Callbacks{
        OnEscalation: func(s coordination.Snapshot) {
            // alert ops
        },
    },
})
c.Register("worker-1")
c.Update("worker-1", 0.4)
```

Redis-backed (interoperable with Python and Node references):

```go
// RedisClient is a structural interface — any client satisfying
// Eval / HSet / HKeys works (go-redis/v9, redigo, custom implementations).
c, _ := coordination.NewRedisCoordinator(coordination.RedisCoordinatorOptions{
    Redis: myRedisClient,  // your structural adapter
    CoordinatorID: "prod-fleet",
})
ctx := context.Background()
c.Register(ctx, "worker-" + os.Getenv("HOSTNAME"))
```

The Lua script used for atomic updates is exported as
`coordination.UpdateAndFetchScript` and is verbatim from
`spec/coordinator/README.md §1.2`.

## Audit sinks

Six SIEM sinks plus the basic ones (memory, null, stdout, fanout,
JSONL file, webhook):

```go
import (
    "github.com/iaiso/iaiso-go/iaiso/audit"
    "github.com/iaiso/iaiso-go/iaiso/audit/sinks/splunk"
    "github.com/iaiso/iaiso-go/iaiso/audit/sinks/datadog"
    "github.com/iaiso/iaiso-go/iaiso/audit/sinks/loki"
    "github.com/iaiso/iaiso-go/iaiso/audit/sinks/elastic"
    "github.com/iaiso/iaiso-go/iaiso/audit/sinks/sumo"
    "github.com/iaiso/iaiso-go/iaiso/audit/sinks/newrelic"
)

sink := audit.NewFanoutSink(
    audit.NewJSONLFileSink("./audit.jsonl"),
    splunk.New(splunk.Options{
        URL:   "https://splunk.example.com:8088/services/collector/event",
        Token: os.Getenv("SPLUNK_HEC_TOKEN"),
        Index: "iaiso",
    }),
    datadog.New(datadog.Options{
        URL:    "https://http-intake.logs.datadoghq.com/api/v2/logs",
        APIKey: os.Getenv("DD_API_KEY"),
        Service: "iaiso",
    }),
    loki.New(loki.Options{
        URL:    "https://logs.grafana.net/loki/api/v1/push",
        Labels: map[string]string{"job": "iaiso", "env": "prod"},
    }),
)
```

Each SIEM package exports a pure `Payload` function so operators can
validate the wire format without network I/O.

## OIDC identity

```go
import "github.com/iaiso/iaiso-go/iaiso/identity"

verifier, _ := identity.NewVerifier(identity.OktaConfig("acme.okta.com", "api://iaiso"))
issuer := consent.NewIssuer(consent.IssuerOptions{...})

scope, err := identity.IssueFromOIDC(ctx, identity.IssueFromOIDCParams{
    Verifier: verifier,
    Issuer:   issuer,
    Token:    incomingOIDCAccessToken,
    Mapping: identity.ScopeMapping{
        DirectClaims: []string{"scp", "permissions"},
        GroupToScopes: map[string][]string{
            "engineers": {"tools.search", "tools.fetch"},
            "admins":    {"admin"},
        },
    },
    TTLSeconds:  3600,
    ExecutionID: execID,
})
```

Preset factories: `OktaConfig`, `Auth0Config`, `AzureADConfig`. The
generic `ProviderConfig` works against any conforming OIDC provider.

## Metrics and tracing

`metrics.PrometheusSink` wires audit events into your Prometheus
client (any client implementing the structural `Counter` /
`CounterVec` / `Gauge` / `GaugeVec` / `Histogram` interfaces — the
official `prometheus/client_golang` does, with a thin wrapper).

`observability.OtelSpanSink` opens one OpenTelemetry span per execution
and attaches every audit event as a span event.

## Admin CLI

```bash
go install github.com/iaiso/iaiso-go/cmd/iaiso@latest
go install github.com/iaiso/iaiso-go/cmd/iaiso-conformance@latest
```

```
iaiso policy validate ./iaiso.policy.json
iaiso policy template ./iaiso.policy.json
iaiso consent issue user-42 tools.search,tools.fetch 3600  # needs IAISO_HS256_SECRET
iaiso consent verify <token>
iaiso audit tail ./iaiso-audit.jsonl
iaiso audit stats ./iaiso-audit.jsonl
iaiso coordinator demo
iaiso conformance ./spec
iaiso-conformance ./spec
```

## Conformance

```bash
go run ./cmd/iaiso-conformance ./spec

# Output:
# [PASS] pressure: 20/20
# [PASS] consent: 23/23
# [PASS] events: 7/7
# [PASS] policy: 17/17
#
# conformance: 67/67 vectors passed
```

Or programmatically:

```go
results, _ := conformance.RunAll("./spec")
pass, total := results.CountPassed()
```

### Float tolerance

Pressure math is specified to real-number semantics with a `1e-9`
absolute tolerance for floating-point implementations
(see `spec/README.md`). This port meets the tolerance with
straightforward IEEE-754 evaluation.

### Cross-language parity

Events emitted by this port validate against the same JSON Schemas
(`spec/events/envelope.schema.json`, `spec/events/payloads.schema.json`)
as the Python and Node references. Consent tokens issued by this port
verify against the Python `ConsentVerifier` and Node `ConsentVerifier`
(and vice versa) given the same key and algorithm. Redis coordinator
state is interoperable across all three runtimes using the same
`(key_prefix, coordinator_id)` tuple.

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
└── iaiso/
    ├── core/                          # engine, BoundedExecution
    ├── consent/                       # JWT issuer/verifier
    ├── audit/                         # event envelope + base sinks
    │   └── sinks/
    │       ├── splunk/
    │       ├── datadog/
    │       ├── loki/
    │       ├── elastic/
    │       ├── sumo/
    │       └── newrelic/
    ├── policy/                        # policy loader (JSON + YAML)
    ├── coordination/                  # in-memory + Redis
    ├── middleware/                    # 7 LLM providers
    │   ├── anthropic/
    │   ├── openai/
    │   ├── gemini/
    │   ├── bedrock/
    │   ├── mistral/
    │   ├── cohere/
    │   └── litellm/
    ├── identity/                      # OIDC verifier + scope mapping
    ├── metrics/                       # Prometheus sink
    ├── observability/                 # OpenTelemetry tracing sink
    ├── conformance/                   # vector runner
    └── cli/                           # admin CLI implementation
```

## Development

```bash
go build ./...                     # compile all packages
go test ./...                      # run unit tests + conformance
go run ./cmd/iaiso-conformance ./spec
```

## Versioning

- Module version tracks SDK features (`v0.1.0`, `v0.2.0`, …).
- **Spec version** is `1.0`, defined in `./spec/VERSION`. A MINOR spec
  bump never breaks existing vectors; a MAJOR spec bump ships a
  migration guide.
- Breaking changes in the public API are signaled by a MAJOR module bump.

## License

Apache-2.0. See [LICENSE](LICENSE).

## Links

- Main repository: https://github.com/SmartTasksOrg/IAISO
- Framework specification: `../../vision/README.md` in the repo
- Python reference SDK: `../iaiso-python/README.md` in the repo
- Node reference SDK: `../iaiso-node/README.md` in the repo
- Conformance porting guide: `../docs/CONFORMANCE.md` in the repo
- Normative specification: `../spec/` in the repo
