#!/usr/bin/env python
"""End-to-end calibration study.

Runs the full pipeline:
    1. Load trajectory JSONL files (one or more).
    2. Shuffle and split 70/30 into calibration and held-out sets.
    3. Calibrate on the calibration set.
    4. Validate recommended config on the held-out set.
    5. Write a study report (JSON + markdown) with full provenance.

This is designed to produce a self-contained, auditable report of how
a given PressureConfig was derived, so the resulting calibration can
be reviewed by someone who wasn't in the room.

Usage:
    python scripts/run_calibration_study.py \\
        --input trajectories/swebench.jsonl trajectories/gaia.jsonl \\
        --study-name swebench-gaia-2026-04 \\
        --output-dir ./calibration_studies/ \\
        --seed 42

What gets written to output-dir/study-name/:
    config.json           — the recommended PressureConfig
    report.md             — human-readable summary
    report.json           — machine-readable summary with all metrics
    calibration_set.jsonl — the actual trajectories used for calibration
    held_out_set.jsonl    — the held-out trajectories

The last two let anyone reproduce the study.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import random
from datetime import datetime, timezone
from pathlib import Path

from iaiso.calibration import calibrate, load_trajectories, save_trajectories, validate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0] if __doc__ else "")
    parser.add_argument("--input", nargs="+", required=True,
                        help="One or more trajectory JSONL files to combine")
    parser.add_argument("--study-name", required=True,
                        help="Identifier for this study (used for output dir)")
    parser.add_argument("--output-dir", default="./calibration_studies",
                        help="Root directory for study outputs")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for calibration/holdout split")
    parser.add_argument("--calibration-fraction", type=float, default=0.7,
                        help="Fraction of trajectories for calibration "
                             "(remainder held out)")
    args = parser.parse_args()

    out_dir = Path(args.output_dir) / args.study_name
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load
    all_trajectories = []
    for input_path in args.input:
        trajs = load_trajectories(input_path)
        print(f"Loaded {len(trajs)} trajectories from {input_path}")
        all_trajectories.extend(trajs)
    print(f"Total: {len(all_trajectories)} trajectories")

    # Filter out ambiguous for the split (they'd be unused anyway).
    labeled = [t for t in all_trajectories
               if t.label in ("benign", "runaway")]
    print(f"After filtering ambiguous: {len(labeled)}")

    benign = [t for t in labeled if t.label == "benign"]
    runaway = [t for t in labeled if t.label == "runaway"]
    print(f"  {len(benign)} benign, {len(runaway)} runaway")

    if len(benign) < 20 or len(runaway) < 20:
        print("WARNING: insufficient labeled data. "
              "Results will be unreliable.")

    # 2. Stratified split — preserve class balance in both sets
    rng = random.Random(args.seed)
    rng.shuffle(benign)
    rng.shuffle(runaway)

    n_benign_cal = int(len(benign) * args.calibration_fraction)
    n_runaway_cal = int(len(runaway) * args.calibration_fraction)

    cal_set = benign[:n_benign_cal] + runaway[:n_runaway_cal]
    held_set = benign[n_benign_cal:] + runaway[n_runaway_cal:]
    rng.shuffle(cal_set)
    rng.shuffle(held_set)

    print(f"Calibration set: {len(cal_set)} "
          f"({n_benign_cal} benign, {n_runaway_cal} runaway)")
    print(f"Held-out set:    {len(held_set)} "
          f"({len(benign) - n_benign_cal} benign, "
          f"{len(runaway) - n_runaway_cal} runaway)")

    save_trajectories(cal_set, out_dir / "calibration_set.jsonl")
    save_trajectories(held_set, out_dir / "held_out_set.jsonl")

    # 3. Calibrate
    print("\nRunning calibration...")
    result = calibrate(cal_set)

    # 4. Validate (only if held_set has both classes)
    held_benign = [t for t in held_set if t.label == "benign"]
    held_runaway = [t for t in held_set if t.label == "runaway"]
    held_metrics: dict[str, float] | None = None
    if held_benign and held_runaway:
        print("\nValidating on held-out set...")
        held_metrics = validate(held_set, result.config)
    else:
        print("\nHeld-out set lacks one of the classes; skipping validation.")

    # 5. Write outputs
    cfg_dict = dataclasses.asdict(result.config)
    with (out_dir / "config.json").open("w") as f:
        json.dump({"config": cfg_dict}, f, indent=2)

    report_json = {
        "study_name": args.study_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "inputs": list(args.input),
        "seed": args.seed,
        "calibration_fraction": args.calibration_fraction,
        "dataset": {
            "total_loaded": len(all_trajectories),
            "labeled": len(labeled),
            "benign": len(benign),
            "runaway": len(runaway),
            "calibration_size": len(cal_set),
            "held_out_size": len(held_set),
        },
        "calibration_result": {
            "config": cfg_dict,
            "escalation_threshold": result.escalation_threshold,
            "release_threshold": result.release_threshold,
            "f1_at_threshold": result.f1_at_threshold,
            "benign_peak_p95": result.benign_peak_p95,
            "benign_peak_p99": result.benign_peak_p99,
            "runaway_peak_p05": result.runaway_peak_p05,
            "runaway_peak_p50": result.runaway_peak_p50,
            "gap": result.gap,
            "warnings": result.warnings,
        },
        "held_out_validation": held_metrics,
    }
    with (out_dir / "report.json").open("w") as f:
        json.dump(report_json, f, indent=2)

    # Markdown report
    md_lines = [
        f"# Calibration study: {args.study_name}",
        "",
        f"Created: {report_json['created_at']}",
        f"Seed: {args.seed}",
        "",
        "## Inputs",
        "",
    ]
    for inp in args.input:
        md_lines.append(f"- `{inp}`")
    md_lines.extend([
        "",
        "## Dataset",
        "",
        f"- Total loaded: {report_json['dataset']['total_loaded']}",
        f"- Labeled (benign+runaway): {report_json['dataset']['labeled']}",
        f"- Benign: {report_json['dataset']['benign']}",
        f"- Runaway: {report_json['dataset']['runaway']}",
        f"- Calibration set: {report_json['dataset']['calibration_size']}",
        f"- Held-out set: {report_json['dataset']['held_out_size']}",
        "",
        "## Recommended configuration",
        "",
        "```json",
        json.dumps(cfg_dict, indent=2),
        "```",
        "",
        "## Calibration metrics",
        "",
        f"- Gap (runaway_p05 - benign_p95): {result.gap:+.4f}",
        f"- F1 at threshold: {result.f1_at_threshold:.4f}",
        f"- Benign peak p95: {result.benign_peak_p95:.4f}",
        f"- Benign peak p99: {result.benign_peak_p99:.4f}",
        f"- Runaway peak p05: {result.runaway_peak_p05:.4f}",
        f"- Runaway peak p50: {result.runaway_peak_p50:.4f}",
        "",
    ])
    if held_metrics:
        md_lines.extend([
            "## Held-out validation",
            "",
            f"- TPR (recall on runaway): {held_metrics['tpr']:.4f}",
            f"- FPR (false alarm on benign): {held_metrics['fpr']:.4f}",
            f"- F1: {held_metrics['f1']:.4f}",
            f"- Benign peak mean ± stdev: "
            f"{held_metrics['benign_peak_mean']:.3f} "
            f"± {held_metrics['benign_peak_stdev']:.3f}",
            f"- Runaway peak mean ± stdev: "
            f"{held_metrics['runaway_peak_mean']:.3f} "
            f"± {held_metrics['runaway_peak_stdev']:.3f}",
            "",
        ])
    if result.warnings:
        md_lines.append("## Warnings")
        md_lines.append("")
        for w in result.warnings:
            md_lines.append(f"- ⚠ {w}")
        md_lines.append("")

    md_lines.extend([
        "## Reproducibility",
        "",
        "This study wrote its calibration and held-out splits to "
        "`calibration_set.jsonl` and `held_out_set.jsonl`. To reproduce:",
        "",
        "```bash",
        f"python -m iaiso.calibration calibrate \\",
        f"    --trajectories {out_dir}/calibration_set.jsonl \\",
        f"    --validate {out_dir}/held_out_set.jsonl \\",
        f"    --output {out_dir}/config.json",
        "```",
        "",
    ])

    (out_dir / "report.md").write_text("\n".join(md_lines))

    print(f"\n✓ Study written to {out_dir}/")
    print(f"  config.json")
    print(f"  report.md")
    print(f"  report.json")
    print(f"  calibration_set.jsonl ({len(cal_set)} trajectories)")
    print(f"  held_out_set.jsonl    ({len(held_set)} trajectories)")

    if result.warnings:
        print("\nCalibration warnings:")
        for w in result.warnings:
            print(f"  ⚠ {w}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
