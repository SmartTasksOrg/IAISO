"""Middleware for the Cohere Python SDK (`cohere` v5.x).

Cohere's v5 client exposes `client.chat(...)` and `client.chat_stream(...)`.
Responses include `.meta.billed_units.input_tokens` and `.output_tokens`,
plus `.tool_calls` on the response object itself (not under choices).

Install:  pip install iaiso[cohere]
"""

from __future__ import annotations

from typing import Any

from iaiso.core import BoundedExecution, ExecutionLocked, StepOutcome


class EscalationRaised(RuntimeError):
    pass


class CohereBoundedClient:
    """Wraps `cohere.ClientV2` (or `cohere.Client`) for pressure accounting.

    Example:
        >>> import cohere
        >>> from iaiso import BoundedExecution
        >>> from iaiso.middleware.cohere import CohereBoundedClient
        >>>
        >>> raw = cohere.ClientV2(api_key="...")
        >>> with BoundedExecution.start() as exec_:
        ...     client = CohereBoundedClient(raw, exec_)
        ...     resp = client.chat(
        ...         model="command-r-plus",
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

    def chat(self, **kwargs: Any) -> Any:
        self._preflight()
        response = self._client.chat(**kwargs)
        self._account(response, kwargs.get("model", "cohere"))
        return response

    async def chat_async(self, **kwargs: Any) -> Any:
        self._preflight()
        if hasattr(self._client, "chat_async"):
            response = await self._client.chat_async(**kwargs)
        else:
            # v5 AsyncClientV2 uses .chat coroutine directly
            response = await self._client.chat(**kwargs)
        self._account(response, kwargs.get("model", "cohere"))
        return response

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

    def _account(self, response: Any, model: str) -> None:
        tokens = 0
        meta = getattr(response, "meta", None)
        if meta is not None:
            billed = getattr(meta, "billed_units", None) or getattr(meta, "tokens", None)
            if billed is not None:
                tokens = int(
                    getattr(billed, "input_tokens", 0)
                    + getattr(billed, "output_tokens", 0)
                )

        # Cohere v5: tool_calls on message or on response
        tool_calls = 0
        tc = getattr(response, "tool_calls", None)
        if tc:
            tool_calls = len(tc)
        else:
            msg = getattr(response, "message", None)
            if msg is not None:
                tc2 = getattr(msg, "tool_calls", None) or []
                tool_calls = len(tc2)

        self._execution.record_step(
            tokens=tokens,
            tool_calls=tool_calls,
            tag=f"cohere.chat:{model}",
        )
