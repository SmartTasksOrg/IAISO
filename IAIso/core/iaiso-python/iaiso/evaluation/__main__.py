"""Entry point: `python -m iaiso.evaluation`."""

from __future__ import annotations

import argparse
from pathlib import Path

from iaiso.evaluation import print_summary, run_suite


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the IAIso evaluation harness."
    )
    parser.add_argument(
        "--output-dir",
        default="./eval_output",
        help="Directory to write summary.csv and steps.jsonl.",
    )
    args = parser.parse_args()

    results = run_suite(output_dir=Path(args.output_dir))
    print_summary(results)
    print(f"\nWrote {args.output_dir}/summary.csv and steps.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
