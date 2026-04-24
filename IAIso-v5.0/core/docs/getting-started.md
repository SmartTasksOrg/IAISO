# Getting Started with IAIso

IAIso is an experimental library for bounded agent execution. This guide
walks through the three core patterns.

## Installation

```bash
pip install iaiso
# or, for a specific integration:
pip install iaiso[anthropic]
pip install iaiso[openai]
pip install iaiso[langchain]
```

## Pattern 1: Account for work inside an agent loop

The simplest use: wrap an agent loop so that every unit of work is
accounted for, and pause or abort when pressure escalates.

```python
from iaiso import BoundedExecution, PressureConfig, StepOutcome

with BoundedExecution.start(config=PressureConfig()) as exec_:
    for step in agent_loop():
        # Ask the engine whether we should continue before doing work.
        if exec_.check() is StepOutcome.ESCALATED:
            handle_escalation()  # e.g., pause for human review
            break

        result = do_one_step(step)

        # Report what the step actually cost.
        exec_.record_step(
            tokens=result.tokens,
            tool_calls=result.tool_calls,
            tag=result.name,
        )
```

## Pattern 2: Require explicit consent for actions

Use `ConsentScope` to gate specific operations behind signed, scoped,
expiring tokens.

```python
from iaiso import (
    BoundedExecution,
    ConsentIssuer,
    ConsentVerifier,
    generate_hs256_secret,
)

# Issuance side (e.g., in an auth service):
secret = generate_hs256_secret()  # store in a secrets manager
issuer = ConsentIssuer(signing_key=secret)
token = issuer.issue(
    subject="service-account-42",
    scopes=["tools.search", "tools.fetch"],
    execution_id="exec-abc",
    ttl_seconds=600,
)

# Agent side:
verifier = ConsentVerifier(verification_key=secret)
scope = verifier.verify(token.token, execution_id="exec-abc")

with BoundedExecution.start(
    execution_id="exec-abc",
    consent=scope,
) as exec_:
    exec_.require_scope("tools.search")
    # ... perform the search ...

    exec_.require_scope("tools.delete")  # raises InsufficientScope
```

## Pattern 3: Forward audit events to your observability stack

Every state change emits a structured event. Attach a sink to send events
wherever you need them.

```python
from iaiso import BoundedExecution, FanoutSink, JsonlFileSink, StdoutSink
from iaiso.audit.webhook import WebhookConfig, WebhookSink

webhook = WebhookSink(WebhookConfig(
    url="https://logs.example.com/ingest",
    headers={"Authorization": "Bearer ..."},
    batch_size=50,
))
local_file = JsonlFileSink("./audit.jsonl")
sink = FanoutSink(webhook, local_file)

with BoundedExecution.start(audit_sink=sink) as exec_:
    exec_.record_tokens(500)
    # ... events flow to both the webhook and the file ...

webhook.close()
```

## Pattern 4: Middleware for LLM SDKs

Wrap an Anthropic or OpenAI client to account for every call
automatically.

```python
from anthropic import Anthropic
from iaiso import BoundedExecution, PressureConfig
from iaiso.middleware.anthropic import AnthropicBoundedClient

raw = Anthropic()
with BoundedExecution.start(
    config=PressureConfig(escalation_threshold=0.75),
) as exec_:
    client = AnthropicBoundedClient(raw, exec_, raise_on_escalation=True)

    # Each messages.create() call is automatically accounted for.
    # If pressure crosses the escalation threshold, the next call raises
    # EscalationRaised before hitting the Anthropic API.
    response = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=1024,
        messages=[{"role": "user", "content": "What's the weather?"}],
    )
```

## Running the evaluation harness

The harness compares IAIso against baseline approaches on adversarial
scenarios:

```bash
python -m iaiso.evaluation
```

Outputs `eval_output/summary.csv` and `eval_output/steps.jsonl`. See
`evals/baseline/summary.csv` for the reference numbers shipped with
this version.

## Next steps

- `docs/spec/pressure-model.md` — exact specification of the
  pressure-accumulation equation and lifecycle.
- `docs/spec/consent.md` — JWT format and verification procedure.
- `docs/spec/events.md` — audit event schema.
- `docs/calibration.md` — how to tune coefficients for your workload.
