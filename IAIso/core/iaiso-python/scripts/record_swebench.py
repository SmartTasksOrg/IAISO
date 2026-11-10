"""Instrument a SWE-bench agent run to record IAIso trajectories.

SWE-bench (https://www.swebench.com/) evaluates agents on real GitHub issues
from popular Python repositories. It's a useful benchmark for runaway
detection because:
    - Successful runs have a bounded length (agent converges on a patch).
    - Failed runs often exhibit runaway patterns (tool-call loops,
      repeated file reads, long reasoning spirals).

This script does NOT run SWE-bench itself — SWE-bench has its own harness
(swebench library). Instead, this wraps an existing SWE-bench agent with
trajectory recording and, post-run, labels trajectories based on whether
the agent's patch was marked as resolving the issue.

Usage:

    # Inside your SWE-bench agent's step loop, instead of (or alongside)
    # your normal instrumentation, call:
    #
    #     from scripts.record_swebench import SWEBenchTrajectoryLogger
    #     logger = SWEBenchTrajectoryLogger(
    #         instance_id=instance["instance_id"],
    #         output_path="./trajectories/swebench.jsonl",
    #     )
    #     for step in agent_loop():
    #         logger.observe_step(
    #             tokens=step.llm_tokens,
    #             tool_calls=step.tool_calls,
    #             depth=step.planning_depth,
    #         )
    #     logger.finalize(resolved=eval_result["resolved"])
    #
    # Across your SWE-bench run, this appends one trajectory per instance
    # to the output JSONL file, labeled "benign" if the patch resolved
    # the issue and "runaway" if the agent failed (especially if it hit
    # a token or tool-call ceiling).

After running, feed the JSONL into the calibration CLI:

    python -m iaiso.calibration calibrate \\
        --trajectories ./trajectories/swebench.jsonl \\
        --output ./swebench_config.json \\
        --verbose

Honest caveats:
    - "Benign" == "agent succeeded". Some failed runs are failures for
      reasons unrelated to runaway behavior (the issue is genuinely hard).
      Labeling those as "runaway" will degrade calibration.
    - SWE-bench instances vary widely in difficulty. A single IAIso
      config tuned on SWE-bench-Lite may not transfer to SWE-bench-Verified
      or to production agents on your codebase.
    - Collect at least 30 resolved + 30 unresolved runs for meaningful
      calibration; 100+ of each class is better.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from iaiso.calibration import Trajectory, TrajectoryRecorder


class SWEBenchTrajectoryLogger:
    """Records a single SWE-bench instance run as an IAIso Trajectory.

    Attributes are intentionally minimal — add metadata via the `metadata`
    argument on construction if you want to track additional context
    (model name, agent framework, repo, difficulty).
    """

    def __init__(
        self,
        instance_id: str,
        output_path: str | Path,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._output_path = Path(output_path)
        self._output_path.parent.mkdir(parents=True, exist_ok=True)
        meta = {"benchmark": "swebench", "instance_id": instance_id}
        if metadata:
            meta.update(metadata)
        self._recorder = TrajectoryRecorder(
            run_id=f"swebench:{instance_id}",
            metadata=meta,
        )
        self._last_step_at = time.monotonic()

    def observe_step(
        self,
        tokens: int = 0,
        tool_calls: int = 0,
        depth: int = 0,
    ) -> None:
        """Record one step of the agent's execution.

        Call this once per LLM call, once per tool invocation, or once per
        agent iteration — whichever granularity you want to calibrate at.
        Be consistent: if you record per-LLM-call in calibration, you'll
        want to record per-LLM-call in production.
        """
        now = time.monotonic()
        self._recorder.step(
            tokens=tokens,
            tool_calls=tool_calls,
            depth=depth,
            elapsed_seconds=now - self._last_step_at,
        )
        self._last_step_at = now

    def finalize(
        self,
        *,
        resolved: bool,
        hit_token_limit: bool = False,
        hit_tool_limit: bool = False,
    ) -> Trajectory:
        """Assign a label based on the outcome and append the trajectory
        to the output file.

        Labeling policy:
            - resolved=True → "benign" (agent converged successfully)
            - hit_token_limit or hit_tool_limit → "runaway" (agent exhausted
              its budget without converging — a runaway signal)
            - Otherwise → "ambiguous" (failed for unclear reasons; could
              be too-hard task, not a runaway)

        Customize this policy by passing `label=` directly if you have
        richer outcome signals.
        """
        if resolved:
            label = "benign"
        elif hit_token_limit or hit_tool_limit:
            label = "runaway"
        else:
            label = "ambiguous"

        trajectory = self._recorder.finalize(label)
        with self._output_path.open("a", encoding="utf-8") as f:
            f.write(trajectory.to_json() + "\n")
        return trajectory
