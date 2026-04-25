"""LangChain integration — a callback handler that reports token and tool-call
events into a BoundedExecution.

Usage:
    from langchain_anthropic import ChatAnthropic
    from iaiso import BoundedExecution
    from iaiso.middleware.langchain import IAIsoCallbackHandler

    with BoundedExecution.start() as exec:
        handler = IAIsoCallbackHandler(exec)
        llm = ChatAnthropic(model="claude-opus-4-7", callbacks=[handler])
        result = llm.invoke("hello")

The handler intentionally does not abort runs on escalation — LangChain callbacks
are advisory. For enforcement, check `execution.check()` between steps in your
chain/agent logic, or wrap the underlying LLM with the provider-specific
middleware in `iaiso.middleware.anthropic` / `iaiso.middleware.openai`.

Install:  pip install iaiso[langchain]
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

try:
    from langchain_core.callbacks import BaseCallbackHandler
    from langchain_core.messages import BaseMessage
    from langchain_core.outputs import LLMResult
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "langchain-core is required for iaiso.middleware.langchain. "
        "Install with `pip install iaiso[langchain]`."
    ) from exc

from iaiso.core import BoundedExecution


class IAIsoCallbackHandler(BaseCallbackHandler):
    """LangChain callback handler that accounts for LLM calls and tool uses.

    This handler does not block or raise on escalation. It records events into
    the attached BoundedExecution and emits audit events. Enforcement decisions
    (pause, reset, reject) must be made by the caller between chain steps.
    """

    def __init__(self, execution: BoundedExecution) -> None:
        self._execution = execution

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        tokens = 0
        usage = (response.llm_output or {}).get("token_usage") or {}
        if isinstance(usage, dict):
            tokens = int(
                usage.get("total_tokens")
                or (usage.get("prompt_tokens", 0)
                    + usage.get("completion_tokens", 0))
            )
        self._execution.record_tokens(tokens=tokens, tag=f"langchain.llm:{run_id}")

    def on_tool_end(
        self,
        output: Any,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        self._execution.record_tool_call(
            name=f"langchain.tool:{run_id}", count=1
        )

    def on_chain_end(
        self,
        outputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        # Chain boundaries increment depth accounting by 1 step with depth=1.
        # This lets the pressure model distinguish deep nested plans from
        # shallow ones even when total token count is similar.
        self._execution.record_step(depth=1, tag=f"langchain.chain:{run_id}")
