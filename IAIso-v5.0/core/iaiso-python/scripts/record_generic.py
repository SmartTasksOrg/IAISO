"""Generic trajectory recorder for any agent loop.

Use this when you have a custom agent, a production workload, or a
benchmark without a dedicated recorder script. It's the pattern that
`record_swebench.py` and `record_gaia.py` specialize.

Usage:

    from scripts.record_generic import GenericTrajectoryLogger

    logger = GenericTrajectoryLogger(
        run_id=str(uuid.uuid4()),
        output_path="./trajectories/production.jsonl",
        metadata={"agent_version": "v1.2", "workload": "customer-support"},
    )

    try:
        for step in agent.run(task):
            logger.observe_step(
                tokens=step.tokens,
                tool_calls=step.tool_calls,
                depth=step.depth,
            )
        success = evaluate_outcome(agent.output)
        logger.finalize(label="benign" if success else "ambiguous")
    except AgentRunawayError:
        logger.finalize(label="runaway")

After enough data is collected, calibrate:

    python -m iaiso.calibration calibrate \\
        --trajectories ./trajectories/production.jsonl \\
        --output ./prod_config.json

Recommended practice:
    - Split your trajectory dataset into 70% calibration / 30% held-out.
      Calibrate on the first, validate on the second.
    - Recalibrate periodically (monthly, or after major agent changes).
      Workload drift will silently degrade a stale calibration.
    - Keep raw trajectories — if you need to try a different calibration
      approach later, you want the original recorded data, not just the
      config you derived from it.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from iaiso.calibration import Trajectory, TrajectoryRecorder


class GenericTrajectoryLogger:
    def __init__(
        self,
        run_id: str,
        output_path: str | Path,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._output_path = Path(output_path)
        self._output_path.parent.mkdir(parents=True, exist_ok=True)
        self._recorder = TrajectoryRecorder(
            run_id=run_id,
            metadata=metadata or {},
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

    def finalize(self, label: str) -> Trajectory:
        """Label must be 'benign', 'runaway', or 'ambiguous'.

        Labeling guidance:
            - benign: The agent completed successfully. Token/tool use
              was acceptable and the output was correct.
            - runaway: The agent exhibited pathological behavior — hit a
              budget ceiling, entered a tool-call loop, or otherwise
              should have been stopped by IAIso had it been enforcing.
            - ambiguous: Unclear outcome. Don't use for calibration;
              calibration drops "ambiguous" trajectories.
        """
        trajectory = self._recorder.finalize(label)
        with self._output_path.open("a", encoding="utf-8") as f:
            f.write(trajectory.to_json() + "\n")
        return trajectory
