"""Middleware for Google's Gemini (google-generativeai SDK) and Vertex AI.

Both SDKs expose `model.generate_content(...)` / `generate_content_async`.
Response objects have `usage_metadata.total_token_count` and
`candidates[].content.parts` that may include function-call parts.

This wrapper accounts for tokens from `usage_metadata` and counts
function-call parts as tool calls.

Install:  pip install iaiso[gemini]
"""

from __future__ import annotations

from typing import Any

from iaiso.core import BoundedExecution, ExecutionLocked, StepOutcome


class EscalationRaised(RuntimeError):
    pass


class GeminiBoundedModel:
    """Wraps a google.generativeai.GenerativeModel (or Vertex AI
    GenerativeModel) for pressure accounting.

    Example:
        >>> import google.generativeai as genai
        >>> from iaiso import BoundedExecution
        >>> from iaiso.middleware.gemini import GeminiBoundedModel
        >>>
        >>> model = genai.GenerativeModel("gemini-1.5-pro")
        >>> with BoundedExecution.start() as exec_:
        ...     wrapped = GeminiBoundedModel(model, exec_)
        ...     resp = wrapped.generate_content("hello")

    Works against both:
        - google.generativeai (public Gemini API)
        - vertexai.generative_models (Vertex AI)
    The response shape is the same across both.
    """

    def __init__(
        self,
        model: Any,
        execution: BoundedExecution,
        *,
        raise_on_escalation: bool = False,
    ) -> None:
        self._model = model
        self._execution = execution
        self._raise_on_escalation = raise_on_escalation

    def generate_content(self, *args: Any, **kwargs: Any) -> Any:
        self._preflight()
        response = self._model.generate_content(*args, **kwargs)
        self._account(response)
        return response

    async def generate_content_async(self, *args: Any, **kwargs: Any) -> Any:
        self._preflight()
        response = await self._model.generate_content_async(*args, **kwargs)
        self._account(response)
        return response

    def start_chat(self, *args: Any, **kwargs: Any) -> "_BoundedChatSession":
        """Return a wrapper around a ChatSession."""
        inner = self._model.start_chat(*args, **kwargs)
        return _BoundedChatSession(inner, self._execution,
                                   self._raise_on_escalation)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._model, name)

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

    def _account(self, response: Any) -> None:
        tokens = 0
        meta = getattr(response, "usage_metadata", None)
        if meta is not None:
            tokens = int(getattr(meta, "total_token_count", 0))

        # Count function-call parts across all candidates
        tool_calls = 0
        candidates = getattr(response, "candidates", None) or []
        for cand in candidates:
            content = getattr(cand, "content", None)
            if content is None:
                continue
            parts = getattr(content, "parts", None) or []
            for part in parts:
                if getattr(part, "function_call", None) is not None:
                    tool_calls += 1

        model_name = str(getattr(self._model, "model_name", "gemini"))
        self._execution.record_step(
            tokens=tokens,
            tool_calls=tool_calls,
            tag=f"gemini.generate:{model_name}",
        )


class _BoundedChatSession:
    """Wraps a Gemini ChatSession so `send_message` is accounted."""

    def __init__(
        self,
        session: Any,
        execution: BoundedExecution,
        raise_on_escalation: bool,
    ) -> None:
        self._session = session
        self._execution = execution
        self._raise_on_escalation = raise_on_escalation
        self._parent = GeminiBoundedModel.__new__(GeminiBoundedModel)
        self._parent._model = None  # unused
        self._parent._execution = execution
        self._parent._raise_on_escalation = raise_on_escalation

    def send_message(self, *args: Any, **kwargs: Any) -> Any:
        self._parent._preflight()
        response = self._session.send_message(*args, **kwargs)
        self._parent._account(response)
        return response

    async def send_message_async(self, *args: Any, **kwargs: Any) -> Any:
        self._parent._preflight()
        response = await self._session.send_message_async(*args, **kwargs)
        self._parent._account(response)
        return response

    def __getattr__(self, name: str) -> Any:
        return getattr(self._session, name)
