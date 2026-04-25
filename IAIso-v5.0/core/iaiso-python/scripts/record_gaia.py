"""Instrument a GAIA benchmark run to record IAIso trajectories.

GAIA (https://huggingface.co/gaia-benchmark) evaluates agents on
multi-step reasoning tasks with tool use. It's complementary to SWE-bench
for IAIso calibration because GAIA tasks span web browsing, file parsing,
math, and multi-modal reasoning — a broader tool-use surface.

This script does NOT run GAIA itself. GAIA is distributed on Hugging Face
with its own evaluation harness. This module wraps your agent's step
loop with trajectory recording, and labels based on final answer correctness.

Usage:

    from scripts.record_gaia import GAIATrajectoryLogger

    for task in gaia_tasks:
        logger = GAIATrajectoryLogger(
            task_id=task["task_id"],
            level=task["Level"],
            output_path="./trajectories/gaia.jsonl",
        )
        agent = build_agent()
        for step in agent.run(task):
            logger.observe_step(
                tokens=step.tokens,
                tool_calls=step.tool_calls,
                depth=step.depth,
            )
        final_answer = agent.final_answer()
        logger.finalize(
            correct=(final_answer.strip() == task["Final answer"].strip()),
        )

Calibrate:

    python -m iaiso.calibration calibrate \\
        --trajectories ./trajectories/gaia.jsonl \\
        --output ./gaia_config.json

Honest caveats:
    - GAIA has 3 difficulty levels. Calibrating on a mix may produce a
      config that's too lax for Level 1 and too tight for Level 3. Consider
      separate calibrations per level.
    - "correct" can be a weak signal for runaway behavior — an agent can
      give a wrong final answer via efficient bad reasoning, which is NOT
      a runaway. If possible, also track whether the agent hit a step
      budget ceiling (that IS a runaway signal).
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from iaiso.calibration import Trajectory, TrajectoryRecorder


class GAIATrajectoryLogger:
    def __init__(
        self,
        task_id: str,
        output_path: str | Path,
        level: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._output_path = Path(output_path)
        self._output_path.parent.mkdir(parents=True, exist_ok=True)
        meta = {"benchmark": "gaia", "task_id": task_id}
        if level is not None:
            meta["level"] = level
        if metadata:
            meta.update(metadata)
        self._recorder = TrajectoryRecorder(
            run_id=f"gaia:{task_id}",
            metadata=meta,
        )
        self._last_step_at = time.monotonic()

    def observe_step(
        self,
        tokens: int = 0,
        tool_calls: int = 0,
        depth: int = 0,
    ) -> None:
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
        correct: bool,
        hit_step_budget: bool = False,
    ) -> Trajectory:
        """Label and write the trajectory.

        Policy:
            - correct=True → "benign"
            - hit_step_budget=True → "runaway"
            - otherwise → "ambiguous"
        """
        if correct:
            label = "benign"
        elif hit_step_budget:
            label = "runaway"
        else:
            label = "ambiguous"

        trajectory = self._recorder.finalize(label)
        with self._output_path.open("a", encoding="utf-8") as f:
            f.write(trajectory.to_json() + "\n")
        return trajectory
