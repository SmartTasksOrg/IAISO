"""Middleware for AWS Bedrock Runtime (boto3 `bedrock-runtime` client).

Bedrock exposes two main invocation shapes:
    1. `invoke_model` / `invoke_model_with_response_stream` — raw
       provider-specific JSON body, response body also provider-specific.
    2. `converse` / `converse_stream` — unified Converse API across all
       providers. Response has `.usage.inputTokens`/`.usage.outputTokens`
       and `.output.message.content[].toolUse` for tool calls. This is
       the preferred path and what this wrapper optimizes for.

Install:  pip install iaiso[bedrock]
"""

from __future__ import annotations

import json
from typing import Any

from iaiso.core import BoundedExecution, ExecutionLocked, StepOutcome


class EscalationRaised(RuntimeError):
    pass


class BedrockBoundedClient:
    """Wraps a boto3 bedrock-runtime client.

    Example:
        >>> import boto3
        >>> from iaiso import BoundedExecution
        >>> from iaiso.middleware.bedrock import BedrockBoundedClient
        >>>
        >>> raw = boto3.client("bedrock-runtime", region_name="us-east-1")
        >>> with BoundedExecution.start() as exec_:
        ...     client = BedrockBoundedClient(raw, exec_)
        ...     resp = client.converse(
        ...         modelId="anthropic.claude-opus-4-7",
        ...         messages=[{"role": "user", "content": [{"text": "hi"}]}],
        ...     )
    """

    def __init__(
        self,
        client: Any,
        execution: BoundedExecution,
        *,
        raise_on_escalation: bool = False,
    ) -> None:
        self._client = client
        self._execution = execution
        self._raise_on_escalation = raise_on_escalation

    def converse(self, **kwargs: Any) -> Any:
        """Call the Converse API. Accounts for tokens from usage object."""
        self._preflight()
        response = self._client.converse(**kwargs)
        self._account_converse(response, kwargs.get("modelId", "unknown"))
        return response

    def invoke_model(self, **kwargs: Any) -> Any:
        """Call invoke_model. Accounts from provider-specific response body.

        We try to parse the body for usage info; if parsing fails we still
        record a step with tokens=0 so the call shows up in audit, just
        without token accounting. This is more useful than failing silently.
        """
        self._preflight()
        response = self._client.invoke_model(**kwargs)
        self._account_invoke(response, kwargs.get("modelId", "unknown"))
        return response

    def converse_stream(self, **kwargs: Any) -> Any:
        """Streaming Converse. Usage arrives in the final event."""
        self._preflight()
        response = self._client.converse_stream(**kwargs)
        # For streaming, we don't know tokens until the stream is consumed.
        # Best practice: wrap the stream and account at metadata event.
        return _StreamingConverseWrapper(
            response, self._execution, kwargs.get("modelId", "unknown"),
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)

    def _preflight(self) -> None:
        pre = self._execution.check()
        if pre is StepOutcome.LOCKED:
            raise ExecutionLocked(
                f"execution {self._execution.engine.execution_id} is locked"
            )
        if pre is StepOutcome.ESCALATED and self._raise_on_escalation:
            raise EscalationRaised(
                f"execution escalated at pressure "
                f"{self._execution.engine.pressure:.3f}"
            )

    def _account_converse(self, response: Any, model_id: str) -> None:
        usage = response.get("usage", {}) if isinstance(response, dict) else {}
        tokens = int(usage.get("inputTokens", 0)) + int(usage.get("outputTokens", 0))

        tool_calls = 0
        output = response.get("output", {}) if isinstance(response, dict) else {}
        message = output.get("message", {}) if isinstance(output, dict) else {}
        content_blocks = message.get("content", []) if isinstance(message, dict) else []
        for block in content_blocks:
            if isinstance(block, dict) and "toolUse" in block:
                tool_calls += 1

        self._execution.record_step(
            tokens=tokens,
            tool_calls=tool_calls,
            tag=f"bedrock.converse:{model_id}",
        )

    def _account_invoke(self, response: Any, model_id: str) -> None:
        tokens = 0
        try:
            body = response.get("body") if isinstance(response, dict) else None
            if body is not None:
                # body is a StreamingBody; read once. Caller will need the
                # bytes, so we have to be careful. We read and restore.
                data = body.read() if hasattr(body, "read") else body
                try:
                    parsed = json.loads(data)
                    # Anthropic on Bedrock: usage.input_tokens / output_tokens
                    # Cohere: tokens
                    # Titan/Amazon: inputTextTokenCount / results[].tokenCount
                    if "usage" in parsed:
                        u = parsed["usage"]
                        tokens = int(u.get("input_tokens", 0)) + int(u.get("output_tokens", 0))
                    elif "inputTextTokenCount" in parsed:
                        tokens = int(parsed.get("inputTextTokenCount", 0))
                        for r in parsed.get("results", []):
                            tokens += int(r.get("tokenCount", 0))
                except json.JSONDecodeError:
                    pass
                # Restore the body so caller can still read it. boto3's
                # StreamingBody is single-use so we wrap the bytes.
                import io
                response["body"] = io.BytesIO(data)
        except Exception:  # noqa: BLE001
            pass

        self._execution.record_step(
            tokens=tokens,
            tool_calls=0,
            tag=f"bedrock.invoke_model:{model_id}",
        )


class _StreamingConverseWrapper:
    """Wraps a converse_stream response so tokens are accounted when the
    stream is consumed."""

    def __init__(
        self,
        inner: Any,
        execution: BoundedExecution,
        model_id: str,
    ) -> None:
        self._inner = inner
        self._execution = execution
        self._model_id = model_id

    def __iter__(self) -> Any:
        stream = self._inner.get("stream") if isinstance(self._inner, dict) else self._inner
        for event in stream:
            yield event
            if isinstance(event, dict) and "metadata" in event:
                meta = event["metadata"]
                usage = meta.get("usage", {}) if isinstance(meta, dict) else {}
                tokens = (int(usage.get("inputTokens", 0))
                          + int(usage.get("outputTokens", 0)))
                self._execution.record_step(
                    tokens=tokens,
                    tag=f"bedrock.converse_stream:{self._model_id}",
                )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)
