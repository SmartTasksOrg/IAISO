"""Middleware for the OpenAI Python SDK (v1.x).

Wraps `openai.OpenAI` and `openai.AsyncOpenAI` so that every chat completion
call is accounted for. Tokens are read from `response.usage`; tool calls are
counted from `choice.message.tool_calls`.

Install:  pip install iaiso[openai]
"""

from __future__ import annotations

from typing import Any

from iaiso.core import BoundedExecution, StepOutcome


class EscalationRaised(RuntimeError):
    """Raised when the execution has reached escalation and
    `raise_on_escalation=True` was set.
    """


class OpenAIBoundedClient:
    """Wraps an OpenAI v1 client for pressure accounting.

    Example:
        >>> from openai import OpenAI
        >>> from iaiso import BoundedExecution
        >>> from iaiso.middleware.openai import OpenAIBoundedClient
        >>>
        >>> raw = OpenAI()
        >>> with BoundedExecution.start() as exec:
        ...     client = OpenAIBoundedClient(raw, exec)
        ...     resp = client.chat.completions.create(
        ...         model="gpt-4o",
        ...         messages=[{"role": "user", "content": "hi"}],
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
        self.chat = _ChatProxy(client.chat, execution, raise_on_escalation)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


class _ChatProxy:
    def __init__(
        self,
        inner: Any,
        execution: BoundedExecution,
        raise_on_escalation: bool,
    ) -> None:
        self._inner = inner
        self._execution = execution
        self._raise_on_escalation = raise_on_escalation
        self.completions = _CompletionsProxy(
            inner.completions, execution, raise_on_escalation
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


class _CompletionsProxy:
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
        self._preflight()
        response = self._inner.create(**kwargs)
        self._account(response)
        return response

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def _preflight(self) -> None:
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

    def _account(self, response: Any) -> None:
        tokens = 0
        usage = getattr(response, "usage", None)
        if usage is not None:
            tokens = int(
                getattr(usage, "total_tokens", 0)
                or getattr(usage, "prompt_tokens", 0)
                + getattr(usage, "completion_tokens", 0)
            )

        tool_calls = 0
        choices = getattr(response, "choices", None) or []
        for choice in choices:
            message = getattr(choice, "message", None)
            if message is None:
                continue
            tc = getattr(message, "tool_calls", None) or []
            tool_calls += len(tc)

        model = str(getattr(response, "model", "unknown"))
        self._execution.record_step(
            tokens=tokens,
            tool_calls=tool_calls,
            tag=f"openai.chat.completions.create:{model}",
        )


class AsyncOpenAIBoundedClient:
    """Async variant. Wraps `openai.AsyncOpenAI`."""

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
        self.chat = _AsyncChatProxy(client.chat, execution, raise_on_escalation)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


class _AsyncChatProxy:
    def __init__(
        self,
        inner: Any,
        execution: BoundedExecution,
        raise_on_escalation: bool,
    ) -> None:
        self._inner = inner
        self._execution = execution
        self._raise_on_escalation = raise_on_escalation
        self.completions = _AsyncCompletionsProxy(
            inner.completions, execution, raise_on_escalation
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


class _AsyncCompletionsProxy(_CompletionsProxy):
    async def create(self, **kwargs: Any) -> Any:  # type: ignore[override]
        self._preflight()
        response = await self._inner.create(**kwargs)
        self._account(response)
        return response
