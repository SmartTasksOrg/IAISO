"""Middleware for the Mistral Python SDK (`mistralai`).

Mistral's official client (v1.x) exposes `client.chat.complete(...)` and
`client.chat.complete_async(...)`. Response shape is OpenAI-like with
`.usage.total_tokens` and `.choices[].message.tool_calls`.

Install:  pip install iaiso[mistral]
"""

from __future__ import annotations

from typing import Any

from iaiso.core import BoundedExecution, ExecutionLocked, StepOutcome


class EscalationRaised(RuntimeError):
    pass


class MistralBoundedClient:
    """Wraps `mistralai.Mistral` for pressure accounting.

    Example:
        >>> from mistralai import Mistral
        >>> from iaiso import BoundedExecution
        >>> from iaiso.middleware.mistral import MistralBoundedClient
        >>>
        >>> raw = Mistral(api_key="...")
        >>> with BoundedExecution.start() as exec_:
        ...     client = MistralBoundedClient(raw, exec_)
        ...     resp = client.chat.complete(
        ...         model="mistral-large-latest",
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

    def complete(self, **kwargs: Any) -> Any:
        self._preflight()
        response = self._inner.complete(**kwargs)
        self._account(response, kwargs.get("model", "mistral"))
        return response

    async def complete_async(self, **kwargs: Any) -> Any:
        self._preflight()
        response = await self._inner.complete_async(**kwargs)
        self._account(response, kwargs.get("model", "mistral"))
        return response

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

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

    def _account(self, response: Any, model: str) -> None:
        tokens = 0
        usage = getattr(response, "usage", None)
        if usage is not None:
            tokens = int(
                getattr(usage, "total_tokens", 0)
                or (getattr(usage, "prompt_tokens", 0)
                    + getattr(usage, "completion_tokens", 0))
            )

        tool_calls = 0
        choices = getattr(response, "choices", None) or []
        for choice in choices:
            msg = getattr(choice, "message", None)
            if msg is None:
                continue
            tc = getattr(msg, "tool_calls", None) or []
            tool_calls += len(tc)

        self._execution.record_step(
            tokens=tokens,
            tool_calls=tool_calls,
            tag=f"mistral.chat.complete:{model}",
        )
