"""End-to-end example: IAIso against a local vLLM server.

Prerequisites:
    1. Install vLLM:
           pip install vllm
    2. Start a vLLM OpenAI-compatible server:
           python -m vllm.entrypoints.openai.api_server \\
               --model meta-llama/Llama-3.2-1B-Instruct \\
               --port 8000
       (Any model works; smaller ones start faster.)
    3. Install IAIso with the OpenAI extra:
           pip install iaiso[openai]
    4. Run this script:
           python examples/self_hosted_vllm.py

What this demonstrates:
    - vLLM exposes OpenAI-compatible /v1/chat/completions.
    - IAIso's existing OpenAI middleware works against it unchanged.
    - Pressure accumulates from the tokens vLLM reports.
    - After enough calls, the execution escalates and then locks.

If you don't have vLLM running locally, the example falls back to
pointing at an unreachable URL and printing what WOULD happen. That's
useful for confirming the IAIso wiring is correct without needing a
GPU.
"""

from __future__ import annotations

import os
import sys

from iaiso import (
    BoundedExecution,
    JsonlFileSink,
    MemorySink,
    PressureConfig,
)

VLLM_URL = os.environ.get("VLLM_URL", "http://localhost:8000/v1")
MODEL = os.environ.get("VLLM_MODEL", "meta-llama/Llama-3.2-1B-Instruct")


def main() -> int:
    try:
        from openai import OpenAI
    except ImportError:
        print("This example requires the openai package. "
              "Install with: pip install iaiso[openai]")
        return 1

    from iaiso.middleware.openai import OpenAIBoundedClient

    # vLLM's OpenAI-compatible server doesn't require a real API key, but
    # the OpenAI client library insists on a non-empty value.
    raw_client = OpenAI(base_url=VLLM_URL, api_key="vllm-local")

    # Tight pressure config so we escalate after a handful of calls —
    # makes the demo quick. For real use, calibrate against your workload
    # (see docs/calibration.md).
    config = PressureConfig(
        token_coefficient=0.05,        # 0.05 per 1000 tokens
        tool_coefficient=0.1,
        dissipation_per_step=0.01,
        escalation_threshold=0.5,
        release_threshold=0.85,
    )

    audit = MemorySink()
    file_audit = JsonlFileSink("./iaiso_vllm_demo.jsonl")

    with BoundedExecution.start(
        config=config,
        audit_sink=audit,
    ) as exec_:
        client = OpenAIBoundedClient(raw_client, exec_)

        prompts = [
            "Write a haiku about caching.",
            "Summarize the TCP three-way handshake in one paragraph.",
            "Explain monads to a skeptic.",
            "Write a 500-word essay on kubernetes operators.",
            "Generate 10 quiz questions about the Roman Empire.",
            "Write a 1000-word short story about a lighthouse keeper.",
        ]

        for i, prompt in enumerate(prompts, start=1):
            snap = exec_.snapshot()
            print(f"\n--- Call {i} | pressure={snap.pressure:.3f} "
                  f"| lifecycle={snap.lifecycle.value} ---")
            print(f"Prompt: {prompt!r}")

            try:
                resp = client.chat.completions.create(
                    model=MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=512,
                )
                usage = resp.usage
                print(f"vLLM reported tokens: prompt={usage.prompt_tokens}, "
                      f"completion={usage.completion_tokens}, "
                      f"total={usage.total_tokens}")
            except Exception as exc:
                # Could be a connection error (vLLM not running) or
                # ExecutionLocked (IAIso stopping further work).
                print(f"Call {i} terminated: {type(exc).__name__}: {exc}")
                if type(exc).__name__ == "ExecutionLocked":
                    print("IAIso locked the execution — this is the demo "
                          "working as intended.")
                    break
                elif "Connection" in type(exc).__name__ or "URL" in str(exc):
                    print(f"vLLM not reachable at {VLLM_URL}. Start vLLM "
                          f"and rerun, or set VLLM_URL env var.")
                    return 0
                else:
                    raise

    # Show what the audit sink captured.
    print("\n--- Audit event summary ---")
    kinds: dict[str, int] = {}
    for event in audit.events:
        kinds[event.kind] = kinds.get(event.kind, 0) + 1
    for kind, count in sorted(kinds.items()):
        print(f"  {kind}: {count}")
    print(f"\nFull audit log also written to: ./iaiso_vllm_demo.jsonl")
    return 0


if __name__ == "__main__":
    sys.exit(main())
