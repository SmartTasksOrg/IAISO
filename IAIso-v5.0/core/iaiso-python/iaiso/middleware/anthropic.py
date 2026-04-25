"""Middleware for the Anthropic Python SDK.

Wraps `anthropic.Anthropic` and `anthropic.AsyncAnthropic` so that every call
to `messages.create` is accounted for in a `BoundedExecution`. Tokens are read
from the response's `usage` field; tool calls are counted from
`response.content` blocks of type `tool_use`.

Install:  pip install iaiso[anthropic]
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from iaiso.core import BoundedExecution, StepOutcome

if TYPE_CHECKING:
    from anthropic import Anthropic, AsyncAnthropic
    from anthropic.types import Message


class AnthropicBoundedClient:
    """Wraps an Anthropic client so calls account for pressure.

    The wrapped client exposes the same `.messages.create()` surface as the
    underlying Anthropic client. Non-wrapped calls (e.g., `.beta.*`, direct
    streaming) pass through unchanged but are NOT accounted for; if you use
    those, account manually via `execution.record_step()`.

    Example:
        >>> from anthropic import Anthropic
        >>> from iaiso import BoundedExecution, PressureConfig
        >>> from iaiso.middleware.anthropic import AnthropicBoundedClient
        >>>
        >>> raw = Anthropic()
        >>> with BoundedExecution.start(config=PressureConfig()) as exec:
        ...     client = AnthropicBoundedClient(raw, exec)
        ...     msg = client.messages.create(
        ...         model="claude-opus-4-7",
        ...         max_tokens=1024,
        ...         messages=[{"role": "user", "content": "hello"}],
        ...     )

    If the execution becomes LOCKED or escalation is configured to raise,
    calls will raise `iaiso.core.ExecutionLocked` or `EscalationRaised`
    before reaching the Anthropic API.
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
        self.messages = _MessagesProxy(
            client.messages, execution, raise_on_escalation
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


class EscalationRaised(RuntimeError):
    """Raised from middleware when the execution has reached escalation and
    `raise_on_escalation=True` was set.
    """


class _MessagesProxy:
    def __init__(
        self,
        inner: Any,
        execution: BoundedExecution,
        raise_on_escalation: bool,
    ) -> None:
        self._inner = inner
        self._execution = execution
        self._raise_on_escalation = raise_on_escalation

    def create(self, **kwargs: Any) -> Any:
        pre = self._execution.check()
        if pre is StepOutcome.LOCKED:
            from iaiso.core import ExecutionLocked
            raise ExecutionLocked(
                f"execution {self._execution.engine.execution_id} is locked"
            )
        if pre is StepOutcome.ESCALATED and self._raise_on_escalation:
            raise EscalationRaised(
                f"execution escalated at pressure "
                f"{self._execution.engine.pressure:.3f}"
            )

        response = self._inner.create(**kwargs)
        self._account(response)
        return response

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def _account(self, response: Any) -> None:
        tokens = 0
        usage = getattr(response, "usage", None)
        if usage is not None:
            tokens = (
                int(getattr(usage, "input_tokens", 0) or 0)
                + int(getattr(usage, "output_tokens", 0) or 0)
            )

        tool_calls = 0
        content = getattr(response, "content", None) or []
        for block in content:
            block_type = getattr(block, "type", None)
            if block_type is None and isinstance(block, dict):
                block_type = block.get("type")
            if block_type == "tool_use":
                tool_calls += 1

        self._execution.record_step(
            tokens=tokens,
            tool_calls=tool_calls,
            tag=f"anthropic.messages.create:{kwargs_model(response)}",
        )


def kwargs_model(response: Any) -> str:
    return str(getattr(response, "model", "unknown"))


class AsyncAnthropicBoundedClient:
    """Async variant. Wraps `anthropic.AsyncAnthropic`."""

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
        self.messages = _AsyncMessagesProxy(
            client.messages, execution, raise_on_escalation
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


class _AsyncMessagesProxy(_MessagesProxy):
    async def create(self, **kwargs: Any) -> Any:  # type: ignore[override]
        pre = self._execution.check()
        if pre is StepOutcome.LOCKED:
            from iaiso.core import ExecutionLocked
            raise ExecutionLocked(
                f"execution {self._execution.engine.execution_id} is locked"
            )
        if pre is StepOutcome.ESCALATED and self._raise_on_escalation:
            raise EscalationRaised(
                f"execution escalated at pressure "
                f"{self._execution.engine.pressure:.3f}"
            )

        response = await self._inner.create(**kwargs)
        self._account(response)
        return response
