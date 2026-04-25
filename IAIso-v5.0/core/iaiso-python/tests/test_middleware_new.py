"""Tests for Gemini, Bedrock, Mistral, and Cohere middleware.

All four use the same mocking pattern: build a fake client/model/response
object whose attribute/dict shape matches the real SDK, and verify that
our wrapper extracts tokens and tool_calls correctly.
"""

from __future__ import annotations

import io
import json
import types
from typing import Any

import pytest

from iaiso import BoundedExecution, MemorySink, PressureConfig


# -- Gemini -----------------------------------------------------------------


def _fake_gemini_response(tokens: int, function_call_names: list[str]) -> Any:
    parts = []
    for name in function_call_names:
        parts.append(types.SimpleNamespace(function_call=types.SimpleNamespace(name=name)))
    # Plus one text part (no function_call)
    parts.append(types.SimpleNamespace(function_call=None, text="ok"))
    return types.SimpleNamespace(
        usage_metadata=types.SimpleNamespace(total_token_count=tokens),
        candidates=[types.SimpleNamespace(
            content=types.SimpleNamespace(parts=parts)
        )],
    )


def test_gemini_accounts_tokens_and_tool_calls() -> None:
    from iaiso.middleware.gemini import GeminiBoundedModel

    class FakeModel:
        model_name = "gemini-1.5-pro"

        def generate_content(self, *args: Any, **kwargs: Any) -> Any:
            return _fake_gemini_response(800, ["search", "calc"])

    sink = MemorySink()
    with BoundedExecution.start(
        config=PressureConfig(token_coefficient=0.1, tool_coefficient=0.1,
                              dissipation_per_step=0.0),
        audit_sink=sink,
    ) as exec_:
        wrapped = GeminiBoundedModel(FakeModel(), exec_)
        wrapped.generate_content("hi")
    # 800 × 0.1/1000 = 0.08 from tokens. 2 tool calls × 0.1 = 0.2. Total = 0.28.
    assert exec_.snapshot().pressure == pytest.approx(0.28, abs=0.01)
    tags = [e.data.get("tag") for e in sink.events if e.kind == "engine.step"]
    assert any("gemini.generate:gemini-1.5-pro" in str(t) for t in tags)


def test_gemini_handles_missing_usage() -> None:
    from iaiso.middleware.gemini import GeminiBoundedModel

    class FakeModel:
        model_name = "gemini-flash"

        def generate_content(self, *args: Any, **kwargs: Any) -> Any:
            return types.SimpleNamespace(usage_metadata=None, candidates=[])

    with BoundedExecution.start(
        config=PressureConfig(dissipation_per_step=0.0),
    ) as exec_:
        wrapped = GeminiBoundedModel(FakeModel(), exec_)
        wrapped.generate_content("hi")
    # tokens=0, tool_calls=0 → pressure stays 0
    assert exec_.snapshot().pressure == 0.0


# -- Bedrock ----------------------------------------------------------------


def test_bedrock_converse_accounts_tokens_and_tools() -> None:
    from iaiso.middleware.bedrock import BedrockBoundedClient

    class FakeBedrock:
        def converse(self, **kwargs: Any) -> dict:
            return {
                "usage": {"inputTokens": 300, "outputTokens": 500},
                "output": {
                    "message": {
                        "content": [
                            {"text": "hi"},
                            {"toolUse": {"name": "search"}},
                            {"toolUse": {"name": "calc"}},
                        ],
                    },
                },
            }

    sink = MemorySink()
    with BoundedExecution.start(
        config=PressureConfig(token_coefficient=0.1, tool_coefficient=0.1,
                              dissipation_per_step=0.0),
        audit_sink=sink,
    ) as exec_:
        client = BedrockBoundedClient(FakeBedrock(), exec_)
        resp = client.converse(
            modelId="anthropic.claude-opus-4-7",
            messages=[{"role": "user", "content": [{"text": "hi"}]}],
        )
    # 800 tokens × 0.1/1000 = 0.08. 2 tools × 0.1 = 0.2. Total = 0.28.
    assert exec_.snapshot().pressure == pytest.approx(0.28, abs=0.01)
    tags = [e.data.get("tag") for e in sink.events if e.kind == "engine.step"]
    assert any("bedrock.converse:anthropic.claude-opus-4-7" in str(t) for t in tags)


def test_bedrock_invoke_model_parses_anthropic_body() -> None:
    from iaiso.middleware.bedrock import BedrockBoundedClient

    class FakeStreamingBody:
        def __init__(self, data: bytes) -> None:
            self._data = data

        def read(self) -> bytes:
            return self._data

    class FakeBedrock:
        def invoke_model(self, **kwargs: Any) -> dict:
            body = json.dumps({
                "usage": {"input_tokens": 200, "output_tokens": 400},
                "content": [{"type": "text", "text": "ok"}],
            }).encode()
            return {"body": FakeStreamingBody(body),
                    "contentType": "application/json"}

    with BoundedExecution.start(
        config=PressureConfig(token_coefficient=0.1,
                              dissipation_per_step=0.0),
    ) as exec_:
        client = BedrockBoundedClient(FakeBedrock(), exec_)
        resp = client.invoke_model(
            modelId="anthropic.claude-opus-4-7",
            body="{}",
        )
    # 600 tokens × 0.1/1000 = 0.06
    assert exec_.snapshot().pressure == pytest.approx(0.06, abs=0.005)
    # Body should still be readable by caller (we restored it)
    assert resp["body"].read() is not None


def test_bedrock_invoke_model_handles_unparseable_body() -> None:
    from iaiso.middleware.bedrock import BedrockBoundedClient

    class FakeBedrock:
        def invoke_model(self, **kwargs: Any) -> dict:
            return {"body": io.BytesIO(b"not json")}

    sink = MemorySink()
    with BoundedExecution.start(audit_sink=sink) as exec_:
        client = BedrockBoundedClient(FakeBedrock(), exec_)
        client.invoke_model(modelId="cohere.command", body="{}")
    # Step should still have been recorded even though body didn't parse
    step_events = [e for e in sink.events if e.kind == "engine.step"]
    assert len(step_events) == 1


# -- Mistral ----------------------------------------------------------------


def test_mistral_accounts_tokens() -> None:
    from iaiso.middleware.mistral import MistralBoundedClient

    class FakeChat:
        def complete(self, **kwargs: Any) -> Any:
            return types.SimpleNamespace(
                usage=types.SimpleNamespace(total_tokens=400),
                choices=[types.SimpleNamespace(message=types.SimpleNamespace(
                    tool_calls=[types.SimpleNamespace(function="x")]
                ))],
            )

    class FakeClient:
        chat = FakeChat()

    sink = MemorySink()
    with BoundedExecution.start(
        config=PressureConfig(token_coefficient=0.1, tool_coefficient=0.1,
                              dissipation_per_step=0.0),
        audit_sink=sink,
    ) as exec_:
        client = MistralBoundedClient(FakeClient(), exec_)
        client.chat.complete(model="mistral-large-latest", messages=[])
    # 400 × 0.1/1000 = 0.04 + 0.1 = 0.14
    assert exec_.snapshot().pressure == pytest.approx(0.14, abs=0.01)


# -- Cohere -----------------------------------------------------------------


def test_cohere_accounts_tokens_from_billed_units() -> None:
    from iaiso.middleware.cohere import CohereBoundedClient

    class FakeClient:
        def chat(self, **kwargs: Any) -> Any:
            return types.SimpleNamespace(
                meta=types.SimpleNamespace(
                    billed_units=types.SimpleNamespace(
                        input_tokens=100, output_tokens=200,
                    ),
                ),
                tool_calls=[
                    types.SimpleNamespace(name="search"),
                    types.SimpleNamespace(name="calc"),
                ],
            )

    sink = MemorySink()
    with BoundedExecution.start(
        config=PressureConfig(token_coefficient=0.1, tool_coefficient=0.1,
                              dissipation_per_step=0.0),
        audit_sink=sink,
    ) as exec_:
        client = CohereBoundedClient(FakeClient(), exec_)
        client.chat(model="command-r-plus", messages=[])
    # 300 × 0.1/1000 = 0.03 + 2×0.1 = 0.23
    assert exec_.snapshot().pressure == pytest.approx(0.23, abs=0.01)
    tags = [e.data.get("tag") for e in sink.events if e.kind == "engine.step"]
    assert any("cohere.chat:command-r-plus" in str(t) for t in tags)


def test_cohere_handles_missing_meta() -> None:
    from iaiso.middleware.cohere import CohereBoundedClient

    class FakeClient:
        def chat(self, **kwargs: Any) -> Any:
            return types.SimpleNamespace(meta=None, tool_calls=None)

    with BoundedExecution.start(
        config=PressureConfig(dissipation_per_step=0.0),
    ) as exec_:
        client = CohereBoundedClient(FakeClient(), exec_)
        client.chat(model="command-r", messages=[])
    # No meta → tokens=0, no tool_calls. Pressure 0.
    assert exec_.snapshot().pressure == 0.0
