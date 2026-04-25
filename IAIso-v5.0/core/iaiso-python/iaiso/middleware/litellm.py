"""Middleware for LiteLLM.

LiteLLM (https://docs.litellm.ai/) is a unified interface across 100+ LLM
providers. Its API is module-level: `litellm.completion(...)`, not a client
class. This middleware mirrors that shape with a `BoundedLiteLLM` holder
that pairs a `BoundedExecution` with LiteLLM calls.

Because LiteLLM normalizes responses to OpenAI's shape (`.usage.total_tokens`,
`.choices[].message.tool_calls`), the accounting logic is identical to the
OpenAI middleware. What this module adds is the model-string-aware tagging
in audit events (`litellm.completion:<provider>/<model>`) and integration
with LiteLLM's `Router` for deployments that route across providers.

Install:  pip install iaiso[litellm]

Known limitations in this first version:
    - Streaming responses are passed through unchanged. The stream
      iterator is NOT wrapped; token counts from streaming calls are
      not accounted unless you pass `stream_options={"include_usage":
      True}` and read the final chunk yourself. If you need streaming +
      accounting, call `execution.record_step(tokens=...)` manually
      after consuming the stream.
    - LiteLLM's proxy mode (running LiteLLM as a standalone HTTP server)
      is out of scope for this wrapper — point the OpenAI client at the
      proxy URL and use `iaiso.middleware.openai` instead.
    - Callback-handler integration (registering a global callback with
      `litellm.callbacks`) is deliberately not provided. Callbacks fire
      in a context-free manner and cannot reliably associate a call with
      a `BoundedExecution`. Use the wrapper at call sites instead.
"""

from __future__ import annotations

from typing import Any

from iaiso.core import BoundedExecution, ExecutionLocked, StepOutcome


class EscalationRaised(RuntimeError):
    """Raised when the execution has reached escalation and
    `raise_on_escalation=True` was set.
    """


class BoundedLiteLLM:
    """Pairs a `BoundedExecution` with LiteLLM's module-level calls.

    Example:
        >>> from iaiso import BoundedExecution
        >>> from iaiso.middleware.litellm import BoundedLiteLLM
        >>>
        >>> with BoundedExecution.start() as exec_:
        ...     llm = BoundedLiteLLM(exec_)
        ...     resp = llm.completion(
        ...         model="gpt-4o",
        ...         messages=[{"role": "user", "content": "hi"}],
        ...     )
        ...     # Also works with any other LiteLLM-supported provider:
        ...     # model="claude-opus-4-7"
        ...     # model="ollama/llama3"
        ...     # model="vertex_ai/gemini-1.5-pro"

    For async code, use `.acompletion()`:
        >>> resp = await llm.acompletion(model="gpt-4o", messages=...)

    For LiteLLM's Router (load balancing across deployments), wrap the
    router's methods the same way — see `BoundedLiteLLMRouter` below.
    """

    def __init__(
        self,
        execution: BoundedExecution,
        *,
        raise_on_escalation: bool = False,
    ) -> None:
        self._execution = execution
        self._raise_on_escalation = raise_on_escalation

    def completion(self, **kwargs: Any) -> Any:
        """Synchronous completion. Mirrors `litellm.completion`."""
        import litellm
        self._preflight()
        response = litellm.completion(**kwargs)
        self._account(response, kwargs.get("model", "unknown"))
        return response

    async def acompletion(self, **kwargs: Any) -> Any:
        """Async completion. Mirrors `litellm.acompletion`."""
        import litellm
        self._preflight()
        response = await litellm.acompletion(**kwargs)
        self._account(response, kwargs.get("model", "unknown"))
        return response

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

    def _account(self, response: Any, requested_model: str) -> None:
        # LiteLLM normalizes to OpenAI response shape: response.usage,
        # response.choices[].message.tool_calls, response.model.
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
            message = getattr(choice, "message", None)
            if message is None:
                continue
            tc = getattr(message, "tool_calls", None) or []
            tool_calls += len(tc)

        # Prefer the provider-reported model, fall back to what the caller
        # requested. LiteLLM sometimes rewrites model strings for routing.
        model = str(getattr(response, "model", None) or requested_model)
        self._execution.record_step(
            tokens=tokens,
            tool_calls=tool_calls,
            tag=f"litellm.completion:{model}",
        )


class BoundedLiteLLMRouter:
    """Wrap a LiteLLM Router instance for pressure accounting.

    LiteLLM's Router handles load balancing, fallbacks, and retries across
    multiple deployments. The wrapped methods (`completion`, `acompletion`)
    have the same shape as the module-level functions and return the same
    response objects.

    Example:
        >>> from litellm import Router
        >>> router = Router(model_list=[...])
        >>> with BoundedExecution.start() as exec_:
        ...     bounded = BoundedLiteLLMRouter(router, exec_)
        ...     resp = bounded.completion(model="gpt-4o", messages=[...])

    Note: retries initiated internally by the Router count as a single
    call from IAIso's perspective — only the final successful (or
    last-attempted) response is accounted. If you want to charge pressure
    per retry, disable Router retries and handle retries at the
    application layer.
    """

    def __init__(
        self,
        router: Any,
        execution: BoundedExecution,
        *,
        raise_on_escalation: bool = False,
    ) -> None:
        self._router = router
        self._delegate = BoundedLiteLLM(
            execution, raise_on_escalation=raise_on_escalation
        )

    def completion(self, **kwargs: Any) -> Any:
        self._delegate._preflight()
        response = self._router.completion(**kwargs)
        self._delegate._account(response, kwargs.get("model", "unknown"))
        return response

    async def acompletion(self, **kwargs: Any) -> Any:
        self._delegate._preflight()
        response = await self._router.acompletion(**kwargs)
        self._delegate._account(response, kwargs.get("model", "unknown"))
        return response

    def __getattr__(self, name: str) -> Any:
        # Let non-accounted methods (health checks, model list, etc.)
        # pass through to the underlying router.
        return getattr(self._router, name)
