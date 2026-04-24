# Self-Hosted LLM Integration

Most self-hosted LLM servers in use today expose OpenAI-compatible HTTP
endpoints: vLLM, Ollama, TGI (in its OpenAI-compat mode), SGLang,
LocalAI, llama.cpp's server mode, and others. For those, **IAIso does
not need a new wrapper** — the existing OpenAI middleware works by
pointing the OpenAI client at a custom `base_url`.

For endpoints that don't speak OpenAI's protocol (raw TGI native API,
NVIDIA Triton, some bespoke internal services), pressure can still be
accounted manually in a few lines.

## The OpenAI-compatible path

### vLLM

```python
from openai import OpenAI
from iaiso import BoundedExecution, PressureConfig
from iaiso.middleware.openai import OpenAIBoundedClient

# Start vLLM with: python -m vllm.entrypoints.openai.api_server \
#     --model meta-llama/Llama-3.1-8B-Instruct --port 8000
raw = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="not-needed-but-required-by-client",
)

with BoundedExecution.start(config=PressureConfig()) as exec_:
    client = OpenAIBoundedClient(raw, exec_)
    resp = client.chat.completions.create(
        model="meta-llama/Llama-3.1-8B-Instruct",
        messages=[{"role": "user", "content": "hi"}],
    )
    # Pressure accounted automatically from resp.usage
```

### Ollama

Ollama exposes an OpenAI-compatible endpoint at `/v1` alongside its
native API:

```python
raw = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama",  # any non-empty string works
)
client = OpenAIBoundedClient(raw, execution)
resp = client.chat.completions.create(
    model="llama3.2",
    messages=[{"role": "user", "content": "hi"}],
)
```

### TGI (Text Generation Inference)

TGI >= 1.4 supports `/v1/chat/completions` in OpenAI-compat mode:

```python
raw = OpenAI(base_url="http://tgi-host:8080/v1", api_key="unused")
client = OpenAIBoundedClient(raw, execution)
```

### SGLang

SGLang's OpenAI-compatible server:

```python
raw = OpenAI(base_url="http://sglang-host:30000/v1", api_key="unused")
client = OpenAIBoundedClient(raw, execution)
```

### LocalAI, llama.cpp server, others

Any server that implements `/v1/chat/completions` with
`response.usage.total_tokens` works. If you're evaluating a new server,
the two things to verify are:

1. Responses include a populated `usage` object with `total_tokens`.
2. The `choices[].message.tool_calls` field is present when the model
   emits tool calls.

If either is missing, accounting will under-count that dimension. See
"Manual accounting" below for a correction pattern.

## Going through LiteLLM

If you're already using LiteLLM as a provider-abstraction layer,
`iaiso.middleware.litellm` covers self-hosted endpoints via LiteLLM's
built-in support (e.g., `model="ollama/llama3.2"`,
`model="hosted_vllm/meta-llama/Llama-3.1-8B-Instruct"`). See the
LiteLLM middleware docstring.

## Manual accounting for non-compat endpoints

For endpoints that don't implement the OpenAI shape — a custom TGI
deployment with the native generate API, Triton with a custom backend,
a bespoke HTTP service — account pressure by hand:

```python
import requests
from iaiso import BoundedExecution, PressureConfig

with BoundedExecution.start(config=PressureConfig()) as exec_:
    # Check that the execution isn't locked before making the call.
    from iaiso.core import StepOutcome, ExecutionLocked
    if exec_.check() is StepOutcome.LOCKED:
        raise ExecutionLocked("execution locked")

    response = requests.post(
        "http://my-custom-llm:8080/generate",
        json={"prompt": "hi", "max_tokens": 100},
        timeout=30.0,
    )
    response.raise_for_status()
    data = response.json()

    # Wherever your server reports token counts — adapt this for your API.
    tokens_in = data.get("prompt_tokens", 0)
    tokens_out = data.get("generated_tokens", 0)
    tool_calls = len(data.get("tool_invocations", []))

    outcome = exec_.record_step(
        tokens=tokens_in + tokens_out,
        tool_calls=tool_calls,
        tag=f"custom_llm:{data.get('model', 'unknown')}",
    )

    if outcome is StepOutcome.ESCALATED:
        # Fleet should be notified / request should be deprioritized
        pass
```

That's the whole pattern — 15 lines per call site. The choice not to
ship a wrapper for this case is deliberate: a wrapper would either be
a trivial `requests.post` helper (which adds nothing the user couldn't
write) or would try to abstract over every possible server shape
(which is where the "plausible-looking integration that doesn't
actually work" failure mode lives).

## Operational notes for self-hosted deployments

- **Token counting accuracy.** Self-hosted servers vary in how they
  count tokens. vLLM and TGI report actual tokenizer output; some
  custom setups report approximations. If your calibrated pressure
  config was derived from hosted-API runs (OpenAI, Anthropic),
  verify token counts match before assuming the config transfers.
- **Streaming.** For streaming responses, set
  `stream_options={"include_usage": True}` on OpenAI-compat servers
  that support it (vLLM does; older TGI may not). Without that, the
  OpenAI middleware will record tokens=0 for streaming calls and
  you'll have to account manually after stream completion.
- **Rate limits.** Self-hosted servers typically don't rate-limit the
  way hosted APIs do. IAIso's pressure-based throttling becomes the
  first line of defense against a runaway agent saturating your
  GPU — which is exactly the use case it's designed for.

## Minimal full example

See `examples/self_hosted_vllm.py` for a runnable script that
exercises the full path end-to-end against a local vLLM server.
