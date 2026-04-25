"""CLI: `python -m iaiso.calibration` — calibrate coefficients on a set of
recorded trajectories.

Usage:
    python -m iaiso.calibration calibrate \\
        --trajectories path/to/trajectories.jsonl \\
        --output path/to/recommended_config.json \\
        [--validate path/to/held_out.jsonl] \\
        [--verbose]

Or to evaluate an existing config on a held-out set:
    python -m iaiso.calibration validate \\
        --config path/to/config.json \\
        --trajectories path/to/held_out.jsonl
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

from iaiso import PressureConfig
from iaiso.calibration import calibrate, load_trajectories, validate


def cmd_calibrate(args: argparse.Namespace) -> int:
    trajectories = load_trajectories(args.trajectories)
    print(f"Loaded {len(trajectories)} trajectories from {args.trajectories}")

    labels = {t.label for t in trajectories}
    by_label = {lbl: sum(1 for t in trajectories if t.label == lbl)
                for lbl in labels}
    print(f"Label distribution: {by_label}")

    if "benign" not in by_label or "runaway" not in by_label:
        print("ERROR: need both 'benign' and 'runaway' labels to calibrate",
              file=sys.stderr)
        return 1

    result = calibrate(trajectories, verbose=args.verbose)

    print("\n--- Calibration result ---")
    print(f"n_benign:                {result.n_benign}")
    print(f"n_runaway:               {result.n_runaway}")
    print(f"benign peak p95:         {result.benign_peak_p95:.4f}")
    print(f"benign peak p99:         {result.benign_peak_p99:.4f}")
    print(f"runaway peak p05:        {result.runaway_peak_p05:.4f}")
    print(f"runaway peak p50:        {result.runaway_peak_p50:.4f}")
    print(f"gap (runaway_p05 - benign_p95): {result.gap:+.4f}")
    print(f"F1 at threshold:         {result.f1_at_threshold:.4f}")
    print(f"Recommended escalation:  {result.escalation_threshold:.4f}")
    print(f"Recommended release:     {result.release_threshold:.4f}")

    print("\n--- Recommended coefficients ---")
    cfg_dict = dataclasses.asdict(result.config)
    for k, v in cfg_dict.items():
        print(f"  {k}: {v}")

    if result.warnings:
        print("\n--- Warnings ---")
        for w in result.warnings:
            print(f"  ⚠ {w}")

    if args.validate:
        held_out = load_trajectories(args.validate)
        print(f"\nLoaded {len(held_out)} held-out trajectories from {args.validate}")
        metrics = validate(held_out, result.config)
        print("\n--- Held-out validation ---")
        print(f"  TPR (recall on runaway): {metrics['tpr']:.4f}")
        print(f"  FPR (false alarm rate):  {metrics['fpr']:.4f}")
        print(f"  F1:                      {metrics['f1']:.4f}")
        print(f"  benign peak mean±stdev:  "
              f"{metrics['benign_peak_mean']:.3f} ± {metrics['benign_peak_stdev']:.3f}")
        print(f"  runaway peak mean±stdev: "
              f"{metrics['runaway_peak_mean']:.3f} ± {metrics['runaway_peak_stdev']:.3f}")

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            json.dump({
                "config": cfg_dict,
                "diagnostics": {
                    "n_benign": result.n_benign,
                    "n_runaway": result.n_runaway,
                    "benign_peak_p95": result.benign_peak_p95,
                    "benign_peak_p99": result.benign_peak_p99,
                    "runaway_peak_p05": result.runaway_peak_p05,
                    "runaway_peak_p50": result.runaway_peak_p50,
                    "gap": result.gap,
                    "f1_at_threshold": result.f1_at_threshold,
                },
                "warnings": result.warnings,
            }, f, indent=2)
        print(f"\nWrote {output_path}")

    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    with Path(args.config).open("r", encoding="utf-8") as f:
        obj = json.load(f)
    cfg = PressureConfig(**obj["config"])
    trajectories = load_trajectories(args.trajectories)
    metrics = validate(trajectories, cfg)
    print(json.dumps(metrics, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="python -m iaiso.calibration",
        description="Calibrate IAIso pressure coefficients on recorded trajectories.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    cp = sub.add_parser("calibrate", help="Fit coefficients to trajectories")
    cp.add_argument("--trajectories", required=True,
                    help="JSONL file with labeled trajectories")
    cp.add_argument("--output", help="Optional JSON file for recommended config")
    cp.add_argument("--validate",
                    help="Optional held-out JSONL file for validation")
    cp.add_argument("--verbose", action="store_true")
    cp.set_defaults(func=cmd_calibrate)

    vp = sub.add_parser("validate", help="Evaluate a config on held-out data")
    vp.add_argument("--config", required=True,
                    help="JSON file containing a PressureConfig")
    vp.add_argument("--trajectories", required=True)
    vp.set_defaults(func=cmd_validate)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
