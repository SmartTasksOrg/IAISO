# iaiso-java

**Java reference SDK for the IAIso bounded-agent-execution framework.**

IAIso adds pressure-based rate limiting, scope-based authorization, and
structured audit logging to LLM agent loops. This is the Java
implementation, conformant to **IAIso spec 1.0**.

> Built on Java 17 (LTS) using Maven for normal users and a hand-rolled
> `javac` build for environments without Maven Central access. Passes
> all **67 spec conformance vectors** plus **50 unit tests**. Wire-format
> compatible with the [Python](../iaiso-python/), [Node](../iaiso-node/),
> [Go](../iaiso-go/), and [Rust](../iaiso-rust/) reference SDKs — same
> audit events, same JWTs, same Redis Lua script.

## Workspace layout

Maven multi-module project. Each capability is its own artifact so users
add only what they need:

```
iaiso-java/
├── pom.xml                        # parent POM
├── README.md, LICENSE, .gitignore
├── build.sh                       # local-build script (no Maven needed)
├── spec/                          # normative spec + conformance vectors
├── iaiso-audit/                   # event envelope + base sinks
├── iaiso-core/                    # pressure engine + BoundedExecution
├── iaiso-consent/                 # JWT issuer/verifier (HS256/RS256)
├── iaiso-policy/                  # JSON policy loader
├── iaiso-coordination/            # in-memory + Redis coordinator
├── iaiso-middleware/              # 7 LLM provider wrappers
├── iaiso-identity/                # OIDC verifier + scope mapping
├── iaiso-metrics/                 # Prometheus sink (structural)
├── iaiso-observability/           # OpenTelemetry sink (structural)
├── iaiso-conformance/             # vector runner
└── iaiso-cli/                     # admin CLI (`iaiso` command)
```

## Install

Add the modules you need to your `pom.xml`:

```xml
<dependency>
    <groupId>io.iaiso</groupId>
    <artifactId>iaiso-core</artifactId>
    <version>0.1.0</version>
</dependency>
<dependency>
    <groupId>io.iaiso</groupId>
    <artifactId>iaiso-consent</artifactId>
    <version>0.1.0</version>
</dependency>
```

Or in Gradle:

```kotlin
implementation("io.iaiso:iaiso-core:0.1.0")
implementation("io.iaiso:iaiso-consent:0.1.0")
```

Requires **Java 17** or later.

The SDK takes a single direct runtime dependency: **Gson** for JSON
parsing. LLM provider clients, Redis, Prometheus, OpenTelemetry, and
HTTP libraries are all integrated via **structural interfaces**, so you
plug in whichever client library you prefer without IAIso pulling those
crates into your dep graph. JWT signing/verification is implemented
in-house using only `javax.crypto.Mac` and `java.security.Signature`.

## Quick start

```java
import io.iaiso.audit.MemorySink;
import io.iaiso.audit.Sink;
import io.iaiso.core.BoundedExecution;
import io.iaiso.core.BoundedExecutionOptions;
import io.iaiso.core.StepOutcome;

public class Demo {
    public static void main(String[] args) {
        Sink sink = new MemorySink();
        BoundedExecution.run(
            BoundedExecutionOptions.builder().auditSink(sink).build(),
            exec -> {
                StepOutcome outcome = exec.recordToolCall("search", 500);
                if (outcome == StepOutcome.ESCALATED) {
                    // Layer 4: request human review per the escalation template
                }
            });
    }
}
```

## LLM middleware

The middleware module exposes seven provider adapters under
`io.iaiso.middleware.*`. Each provider defines a structural `Client`
interface you satisfy with a thin adapter around the upstream SDK:

```java
import io.iaiso.middleware.anthropic.AnthropicMiddleware;
import com.google.gson.JsonObject;

class MyAnthropicAdapter implements AnthropicMiddleware.Client {
    // Wraps anthropic-sdk-java, anthropic-bedrock-java, or any HTTP client.
    public AnthropicMiddleware.Response messagesCreate(JsonObject params) {
        // ... call the upstream SDK, map into AnthropicMiddleware.Response
    }
}

AnthropicMiddleware.BoundedClient bounded = new AnthropicMiddleware.BoundedClient(
    new MyAnthropicAdapter(), exec, AnthropicMiddleware.Options.defaults());
AnthropicMiddleware.Response resp = bounded.messagesCreate(params);
```

The structural pattern keeps the SDK free of any specific provider
library. Adapters: `anthropic`, `openai` (works with any
OpenAI-compatible endpoint including Azure OpenAI, vLLM, TGI, LiteLLM
proxy, Together, Groq), `gemini`, `bedrock` (Converse + InvokeModel),
`mistral`, `cohere`, and `litellm` (proxy-pattern helper).

## Distributed coordination

```java
import io.iaiso.coordination.SharedPressureCoordinator;
import io.iaiso.coordination.RedisCoordinator;
import io.iaiso.coordination.RedisClient;
```

In-memory:

```java
SharedPressureCoordinator c = SharedPressureCoordinator.builder()
    .escalationThreshold(5.0)
    .releaseThreshold(8.0)
    .build();
c.register("worker-1");
c.update("worker-1", 0.4);
```

Redis-backed (interoperable with Python, Node, Go, and Rust references):

```java
// RedisClient is a structural interface — supply an adapter around
// Jedis, Lettuce, Spring Data Redis, or any Redis library.
RedisCoordinator c = RedisCoordinator.builder()
    .redis(myRedisAdapter)
    .coordinatorId("prod-fleet")
    .escalationThreshold(5.0)
    .releaseThreshold(8.0)
    .build();
```

The Lua script used for atomic updates is exported as
`RedisCoordinator.UPDATE_AND_FETCH_SCRIPT` and is verbatim from
`spec/coordinator/README.md §1.2`. **All five reference SDKs ship the
exact same script bytes** — Python, Node, Go, Rust, Java — guaranteeing
fleet coordination across mixed-language environments.

## Audit sinks

The base sinks (`MemorySink`, `NullSink`, `StdoutSink`, `FanoutSink`,
`JsonlFileSink`) live in `io.iaiso.audit` and are always available.

> **Note on SIEM sinks**: SIEM-vendor sinks (Splunk HEC, Datadog Logs,
> Loki, Elasticsearch ECS, Sumo Logic, New Relic Logs) are documented
> and tested in the Python, Node, Go references. The Java port ships
> with the base sinks only in 0.1.0; SIEM sinks are deferred to 0.2.0.
> For now, use `JsonlFileSink` plus a forwarder (Vector, Fluent Bit, or
> any log shipper), or implement a sink for your vendor in two methods —
> the `Sink` interface is just `void emit(Event event)`.

## OIDC identity

```java
import io.iaiso.identity.OidcVerifier;
import io.iaiso.identity.ProviderConfig;
import io.iaiso.identity.ScopeMapping;

ProviderConfig cfg = ProviderConfig.okta("acme.okta.com", "api://my-resource");
// or: ProviderConfig.auth0("acme.auth0.com", "api")
// or: ProviderConfig.azureAd("tenant-id", "api://my-resource", true)
OidcVerifier verifier = new OidcVerifier(cfg);

// Fetch JWKS bytes via java.net.http.HttpClient (or any HTTP library)
// then inject:
verifier.setJwksFromBytes(jwksBytes);

JsonObject claims = verifier.verify(idToken);
List<String> scopes = OidcVerifier.deriveScopes(claims, ScopeMapping.defaults());
```

The crate is HTTP-free — `setJwksFromBytes()` takes pre-fetched bytes,
so users wire in their preferred HTTP client.

## Metrics and tracing

`iaiso-metrics` exposes `PrometheusSink` with structural
`Counter`/`CounterVec`/`Gauge`/`GaugeVec`/`Histogram` interfaces. Adapt
the official `prometheus` Java client.

`iaiso-observability` exposes `OtelSpanSink` with structural `Tracer`
and `Span` interfaces. Adapt the OpenTelemetry Java SDK.

## Admin CLI

The CLI ships as part of the workspace:

```bash
mvn package
java -jar iaiso-cli/target/iaiso-cli-0.1.0.jar --help

# Or via the build.sh local build:
./build.sh build
java -cp "/usr/share/java/gson.jar:build/classes" io.iaiso.cli.Main --help
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
```

## Conformance

```bash
./build.sh test  # builds, runs all 50 unit tests + the 67 spec vectors
```

Or programmatically:

```java
import io.iaiso.conformance.ConformanceRunner;
import io.iaiso.conformance.SectionResults;
import java.nio.file.Paths;

SectionResults r = ConformanceRunner.runAll(Paths.get("./spec"));
System.out.println(r.countPassed() + "/" + r.countTotal());
```

### Float tolerance

Pressure math is specified to real-number semantics with a `1e-9`
absolute tolerance for floating-point implementations
(see `spec/README.md`). This port meets the tolerance with
straightforward IEEE-754 evaluation in `double`.

### Cross-language parity

Audit events emitted by this port serialize byte-identically to the
Python, Node, Go, and Rust references for the same input. JWTs issued
by this port verify against the Python `ConsentVerifier`, Node
`ConsentVerifier`, Go `Verifier`, and Rust `Verifier` (and vice versa)
given the same key and algorithm. Redis coordinator state is
interoperable across all five runtimes using the same
`(key_prefix, coordinator_id)` tuple.

## Development

### With Maven (normal path)

```bash
mvn clean test           # build + test
mvn package              # produces JARs under each module's target/
```

### Without Maven (constrained environments)

If your environment doesn't have Maven Central access, the included
`build.sh` script performs a full build using `javac` directly with
apt-installed JARs:

```bash
sudo apt install -y openjdk-17-jdk libgoogle-gson-java junit4 libhamcrest-java
./build.sh test
```

## Versioning

- Module versions track SDK features (`0.1.0`, `0.2.0`, …).
- **Spec version** is `1.0`, defined in `./spec/VERSION`. A MINOR spec
  bump never breaks existing vectors; a MAJOR spec bump ships a
  migration guide.
- Breaking changes in the public API are signaled by a MAJOR module
  version bump.

## Notable engineering decisions

1. **No JWT library dependency**. JWT signing/verification is implemented
   in-house using `javax.crypto.Mac` (HmacSHA256) and `java.security.Signature`
   (SHA256withRSA). ~150 lines, constant-time signature comparison.
2. **JSON-only policies**. Java has no built-in YAML parser. The Java
   port supports JSON policy files only; convert YAML externally if
   needed (the Python CLI's `iaiso policy template` outputs JSON, or use
   any YAML→JSON converter).
3. **Stable JSON key order via hand-built serialization**. `Event.toJson()`
   writes fields in spec order (`schema_version, execution_id, kind,
   timestamp, data`); the `data` payload uses a `TreeMap` for sorted
   keys; integer doubles serialize as `0` not `0.0` to match the wire
   format of the other reference ports.
4. **Builder pattern throughout**. `PressureConfig.builder()...build()`,
   `EngineOptions`, `StepInput`, `Issuer`, `Verifier`, etc. Java
   idiomatic; defaults baked into builders.
5. **Lifecycle/StepOutcome as Java enums with `wireValue` field**.
   `Lifecycle.RUNNING.toString() == "running"` (lowercase wire format).
   `Lifecycle.fromWire(s)` parses back. Cross-language wire compatibility
   maintained.

## License

Apache-2.0. See [LICENSE](LICENSE).

## Links

- Main repository: https://github.com/SmartTasksOrg/IAISO
- Framework specification: `../../vision/README.md` in the repo
- Python reference SDK: `../iaiso-python/README.md`
- Node.js / TypeScript reference SDK: `../iaiso-node/README.md`
- Go reference SDK: `../iaiso-go/README.md`
- Rust reference SDK: `../iaiso-rust/README.md`
- Conformance porting guide: `../docs/CONFORMANCE.md`
- Normative specification: `../spec/`
