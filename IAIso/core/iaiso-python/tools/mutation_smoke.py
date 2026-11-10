#!/usr/bin/env python3
"""Targeted mutation testing for IAIso's security-critical lines.

Each mutant re-introduces a bug that a reviewer (or an attacker) cares about.
The script applies one mutant at a time to a scratch copy of the package,
runs the security test subset, and requires that the tests FAIL (the mutant
is "killed"). A surviving mutant means a guard can be removed without any
test noticing.

    python tools/mutation_smoke.py            # all mutants
    python tools/mutation_smoke.py --list
    python tools/mutation_smoke.py -k cap     # mutants whose id contains "cap"

Full, untargeted mutation testing: `mutmut run` (config in pyproject.toml).
That takes hours; this takes about a minute.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS = ["tests/test_v2_semantics.py", "tests/test_hardening.py", "tests/test_proxy.py",
         "tests/test_conformance.py", "tests/test_engine.py", "tests/test_fuzz.py",
         "tests/test_enforcement_and_cost.py", "tests/test_consent.py"]

# (id, file, original, mutant). `original` must occur exactly once.
MUTANTS = [
    ("stepinput-allow-negative", "iaiso/core/engine.py",
     "            if v < 0:\n                raise ValueError(f\"StepInput.{name} must be >= 0",
     "            if v < -10**18:\n                raise ValueError(f\"StepInput.{name} must be >= 0"),
    ("stepinput-allow-bool", "iaiso/core/engine.py",
     "if isinstance(v, bool) or not isinstance(v, int):",
     "if not isinstance(v, int):"),
    ("empty-step-dissipates", "iaiso/core/engine.py",
     "if (carries_work or self._cfg.empty_step_dissipation) else 0.0)",
     "if True else 0.0)"),
    ("unpriced-free", "iaiso/core/engine.py",
     "                fallback = max(costs.values())",
     "                fallback = 0.0"),
    ("cap-check-removed", "iaiso/core/engine.py",
     "            if cap and total >= cap:\n                return name",
     "            if False:\n                return name"),
    ("cap-off-by-one", "iaiso/core/engine.py",
     "            if cap and total >= cap:",
     "            if cap and total > cap:"),
    ("cap-precheck-removed", "iaiso/core/engine.py",
     "        if already is not None:\n            # Reset with",
     "        if False:\n            # Reset with"),
    ("release-clears-totals", "iaiso/core/engine.py",
     "        self._pressure = 0.0\n        if self._cfg.post_release_lock:",
     ("        self._pressure = 0.0\n        self._total_tokens = self._total_tool_calls = self._total_steps = 0\n"
      "        if self._cfg.post_release_lock:")),
    ("reserve-ignores-held", "iaiso/core/engine.py",
     "            r_tokens = sum(r.tokens for r in held) + estimate.tokens",
     "            r_tokens = estimate.tokens"),
    ("reserve-ignores-budget", "iaiso/core/engine.py",
     "            if cfg.budget_usd > 0 and self._spend_usd + r_usd + usd > cfg.budget_usd:",
     "            if False:"),
    ("reserve-no-lock", "iaiso/core/engine.py",
     "    def reserve(self, estimate: StepInput) -> Reservation:",
     "    def reserve(self, estimate: StepInput) -> Reservation:  # noqa\n        self._lock = __import__('contextlib').nullcontext()"),
    ("budget-check-removed", "iaiso/core/engine.py",
     "        if self._cfg.budget_usd > 0 and self._spend_usd >= self._cfg.budget_usd:\n            return self._lock_for_budget()",
     "        if False:\n            return self._lock_for_budget()"),
    ("boot-guard-no-cap-removed", "iaiso/core/engine.py",
     "        if not config.has_total_cap:",
     "        if False:"),
    # Not listed: dropping "aud" from options["require"]. That mutant is
    # equivalent (PyJWT already requires `aud` whenever `audience=` is passed,
    # and the constructor guarantees an audience), so no test can kill it; the
    # line is defence in depth. The guard that matters is the constructor:
    ("consent-verifier-audience-optional", "iaiso/consent/__init__.py",
     "            raise ValueError(\"ConsentVerifier needs an audience",
     "            pass\n            if False: raise ValueError(\"ConsentVerifier needs an audience"),
    ("consent-verify-ignores-audience", "iaiso/consent/__init__.py",
     "                audience=self.audience,\n",
     "                audience=None,\n"),
    ("consent-binding-default-off", "iaiso/consent/__init__.py",
     "    require_execution_binding: bool = True",
     "    require_execution_binding: bool = False"),
    ("consent-default-hs256", "iaiso/consent/__init__.py",
     "    if obj is None:\n        raise ValueError(\"no algorithm given",
     "    if obj is None:\n        return \"HS256\"\n        raise ValueError(\"no algorithm given"),
    ("consent-short-hs256-key", "iaiso/consent/__init__.py",
     "        if n < MIN_HS256_KEY_BYTES:",
     "        if n < 1:"),
    ("proxy-allows-stream", "iaiso/proxy/__init__.py",
     "        if body.get(\"stream\"):",
     "        if False:"),
    ("proxy-skips-binding", "iaiso/proxy/__init__.py",
     "            scope = self.cfg.verifier.verify(self._consent_token(headers),\n                                             execution_id=execution_id)",
     "            scope = self.cfg.verifier.verify(self._consent_token(headers))"),
    ("proxy-no-reserve", "iaiso/proxy/__init__.py",
     "            res = engine.reserve(StepInput(tokens=estimate, model=model, tag=\"proxy.reserve\"))",
     "            res = engine.reserve(StepInput(tokens=0, model=model, tag=\"proxy.reserve\"))"),
    ("proxy-usage-missing-free", "iaiso/proxy/__init__.py",
     "            outcome = engine.commit(res, StepInput(tokens=estimate, model=model,\n                                                   tag=\"proxy.usage_missing\"))",
     "            outcome = engine.commit(res, StepInput(tokens=0, model=model,\n                                                   tag=\"proxy.usage_missing\"))"),
    ("proxy-escalation-not-gated", "iaiso/proxy/__init__.py",
     "            if not approved:\n                raise _Refuse(409",
     "            if False:\n                raise _Refuse(409"),
    ("proxy-admin-compare-skipped", "iaiso/proxy/__init__.py",
     "        if not hmac.compare_digest(got.encode(), self.cfg.admin_token.encode()):",
     "        if not got:"),
    ("wrapper-keeps-agent", "iaiso/core/wrapper.py",
     "        self._agent = self._call = self._acall = None",
     "        pass"),
]


def run(selected: list[tuple[str, str, str, str]], python: str) -> list[dict]:
    results = []
    with tempfile.TemporaryDirectory(prefix="iaiso-mut-") as tmp:
        work = Path(tmp) / "pkg"
        shutil.copytree(ROOT, work, ignore=shutil.ignore_patterns(
            ".git", "__pycache__", "*.egg-info", ".pytest_cache", "build", "dist"))
        spec_src = ROOT.parent / "spec"
        if spec_src.exists():
            shutil.copytree(spec_src, Path(tmp) / "spec")
        env = dict(os.environ, PYTHONPATH=str(work), HYPOTHESIS_PROFILE="ci")
        where = subprocess.run([python, "-c", "import iaiso; print(iaiso.__file__)"], cwd=work,
                               env=env, capture_output=True, text=True, check=False).stdout.strip()
        if not where.startswith(str(work)):
            sys.exit(f"iaiso imports from {where!r}, not the scratch copy; use a venv where "
                     "iaiso is not installed (pip uninstall iaiso) or install it non-editable")
        base = subprocess.run([python, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *TESTS],
                              cwd=work, env=env, capture_output=True, text=True, check=False)
        if base.returncode != 0:
            sys.exit("baseline tests fail; fix them before mutation testing:\n" + base.stdout[-2000:])
        for mid, rel, original, mutant in selected:
            f = work / rel
            src = f.read_text()
            if src.count(original) != 1:
                results.append({"id": mid, "status": "stale",
                                "detail": f"original text found {src.count(original)}x in {rel}"})
                continue
            f.write_text(src.replace(original, mutant))
            t0 = time.time()
            r = subprocess.run([python, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *TESTS],
                               cwd=work, env=env, capture_output=True, text=True, timeout=900, check=False)
            f.write_text(src)
            killed = r.returncode != 0
            first_fail = next((ln for ln in r.stdout.splitlines() if ln.startswith("FAILED")), "")
            results.append({"id": mid, "status": "killed" if killed else "SURVIVED",
                            "seconds": round(time.time() - t0, 1), "detail": first_fail[:160]})
            print(f"{'killed  ' if killed else 'SURVIVED'} {mid:32s} {first_fail[:90]}", flush=True)
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-k", help="only mutants whose id contains this")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--json", help="write results here")
    ap.add_argument("--python", default=sys.executable)
    a = ap.parse_args()
    sel = [m for m in MUTANTS if not a.k or a.k in m[0]]
    if a.list:
        for m in sel:
            print(m[0], m[1])
        return 0
    res = run(sel, a.python)
    killed = sum(r["status"] == "killed" for r in res)
    print(f"\nmutation score: {killed}/{len(res)} killed")
    if a.json:
        Path(a.json).write_text(json.dumps({"killed": killed, "total": len(res), "results": res}, indent=2))
    return 0 if killed == len(res) else 1


if __name__ == "__main__":
    raise SystemExit(main())
