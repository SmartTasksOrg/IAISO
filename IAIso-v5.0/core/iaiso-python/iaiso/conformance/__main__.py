"""CLI entry for the IAIso conformance suite.

Usage:
    python -m iaiso.conformance [spec_dir]
    python -m iaiso.conformance spec/ --section pressure
    python -m iaiso.conformance spec/ --verbose

When run without arguments, defaults to ./spec relative to cwd.

Exit code is 0 iff every vector in every invoked section passes.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from iaiso.conformance import (
    run_consent_vectors,
    run_events_vectors,
    run_policy_vectors,
    run_pressure_vectors,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m iaiso.conformance",
        description="Run IAIso conformance test vectors against this implementation.",
    )
    parser.add_argument(
        "spec_dir", nargs="?", default="spec",
        help="Path to the spec/ directory containing vector files. Default: ./spec",
    )
    parser.add_argument(
        "--section", choices=("pressure", "consent", "events", "policy", "all"),
        default="all",
        help="Run only one subsystem's vectors. Default: all.",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Print every vector, not just failures.",
    )
    args = parser.parse_args(argv)

    spec_root = Path(args.spec_dir)
    if not spec_root.exists():
        print(f"error: spec directory not found: {spec_root}", file=sys.stderr)
        return 2

    sections = {
        "pressure": run_pressure_vectors,
        "consent": run_consent_vectors,
        "events": run_events_vectors,
        "policy": run_policy_vectors,
    }

    if args.section != "all":
        sections = {args.section: sections[args.section]}

    total = 0
    failed = 0
    for section_name, runner in sections.items():
        try:
            results = runner(spec_root)
        except FileNotFoundError as exc:
            print(f"[skip] {section_name}: {exc}")
            continue

        section_fail = sum(1 for r in results if not r.passed)
        total += len(results)
        failed += section_fail

        status = "PASS" if section_fail == 0 else "FAIL"
        print(f"[{status}] {section_name}: {len(results) - section_fail}/{len(results)}")

        for r in results:
            if args.verbose or not r.passed:
                print(f"    {r}")

    print()
    if failed == 0:
        print(f"conformance: all {total} vectors passed")
        return 0
    else:
        print(f"conformance: {failed}/{total} vectors failed")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
