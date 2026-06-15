#!/usr/bin/env python3
"""Autonomous Test Orchestrator.

Decides WHICH tests to run based on what changed, then runs them.
Tracks per-component health scores; consistently failing components
are promoted to run first.

Usage:
  python core/orchestrator.py                  # diff vs origin/HEAD, run mapped tests
  python core/orchestrator.py --all            # run the full suite
  python core/orchestrator.py --component api/feeds/admitad.py
  python core/orchestrator.py --report         # print health scores only
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY_FILE = ROOT / "core" / "registry.json"
HEALTH_FILE = ROOT / "logs" / "health_scores.json"


# ── Registry ─────────────────────────────────────────────────────────────────

def _load_registry() -> dict:
    return json.loads(REGISTRY_FILE.read_text())["components"]


# ── Git diff ─────────────────────────────────────────────────────────────────

def _changed_files() -> list[str]:
    """Return files changed vs the upstream/base branch."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "origin/HEAD..."],
            capture_output=True, text=True, cwd=ROOT,
        )
        files = [f.strip() for f in result.stdout.splitlines() if f.strip()]
        if not files:
            # Fallback: uncommitted changes
            result = subprocess.run(
                ["git", "diff", "--name-only"],
                capture_output=True, text=True, cwd=ROOT,
            )
            files = [f.strip() for f in result.stdout.splitlines() if f.strip()]
        return files
    except Exception:
        return []


# ── Health scores ─────────────────────────────────────────────────────────────

def _load_health() -> dict:
    if HEALTH_FILE.exists():
        return json.loads(HEALTH_FILE.read_text())
    return {}


def _save_health(health: dict) -> None:
    HEALTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    HEALTH_FILE.write_text(json.dumps(health, indent=2))


def _update_health(health: dict, component: str, passed: bool) -> None:
    h = health.setdefault(component, {"passes": 0, "failures": 0, "score": 100.0})
    if passed:
        h["passes"] += 1
    else:
        h["failures"] += 1
    total = h["passes"] + h["failures"]
    h["score"] = round(h["passes"] / total * 100, 1) if total else 100.0


# ── Test selection ────────────────────────────────────────────────────────────

def _tests_for_files(changed: list[str], registry: dict) -> list[str]:
    tests: list[str] = []
    seen: set[str] = set()
    for path in changed:
        for component, mapped in registry.items():
            if path == component or path.startswith(component.rstrip("/")):
                for t in mapped:
                    if t not in seen:
                        tests.append(t)
                        seen.add(t)
    return tests


def _prioritise(tests: list[str], health: dict) -> list[str]:
    """Put tests belonging to lowest-health components first."""
    def _score(test: str) -> float:
        # Find lowest health score among components that own this test
        scores = [
            v["score"] for c, mapped in _load_registry().items()
            for t in mapped if t == test
            for v in [health.get(c, {"score": 100.0})]
        ]
        return min(scores) if scores else 100.0

    return sorted(tests, key=_score)


# ── Runner ────────────────────────────────────────────────────────────────────

def _run(tests: list[str]) -> dict[str, bool]:
    results: dict[str, bool] = {}
    for test in tests:
        print(f"  ▶  {test}")
        t0 = time.time()
        r = subprocess.run(
            [sys.executable, "-m", "pytest", test, "-q", "--tb=short"],
            cwd=ROOT, capture_output=True, text=True,
        )
        elapsed = round(time.time() - t0, 1)
        passed = r.returncode == 0
        status = "✅" if passed else "❌"
        print(f"     {status}  {elapsed}s")
        if not passed:
            # Print last 10 lines of output for visibility
            lines = (r.stdout + r.stderr).splitlines()
            for line in lines[-10:]:
                print(f"     {line}")
        results[test] = passed
    return results


# ── Report ───────────────────────────────────────────────────────────────────

def _print_health(health: dict) -> None:
    if not health:
        print("No health data yet. Run some tests first.")
        return
    print(f"\n{'Component':<50} {'Score':>6}  {'P':>5}  {'F':>5}")
    print("-" * 70)
    for component, h in sorted(health.items(), key=lambda x: x[1]["score"]):
        bar = "█" * int(h["score"] / 10) + "░" * (10 - int(h["score"] / 10))
        print(f"{component:<50} {h['score']:>5.1f}%  {h['passes']:>5}  {h['failures']:>5}  {bar}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--all", action="store_true", help="Run the full test suite")
    parser.add_argument("--component", metavar="PATH", help="Run tests for one component")
    parser.add_argument("--report", action="store_true", help="Print health scores and exit")
    args = parser.parse_args()

    health = _load_health()
    registry = _load_registry()

    if args.report:
        _print_health(health)
        return 0

    if args.all:
        tests = [t for mapped in registry.values() for t in mapped]
        tests = list(dict.fromkeys(tests))  # deduplicate, preserve order
    elif args.component:
        tests = registry.get(args.component, [])
        if not tests:
            print(f"No tests mapped for {args.component}")
            return 1
    else:
        changed = _changed_files()
        if not changed:
            print("No changed files detected — running nothing. Use --all to force.")
            return 0
        print(f"Changed files: {changed}")
        tests = _tests_for_files(changed, registry)
        if not tests:
            print("No mapped tests for changed files — consider adding them to core/registry.json")
            return 0

    tests = _prioritise(tests, health)
    print(f"\nRunning {len(tests)} test target(s):\n")

    results = _run(tests)

    # Update health scores
    for test, passed in results.items():
        for component, mapped in registry.items():
            if test in mapped:
                _update_health(health, component, passed)
    _save_health(health)

    passed_count = sum(results.values())
    total = len(results)
    print(f"\n{'='*50}")
    print(f"  {passed_count}/{total} targets passed")
    _print_health(health)

    return 0 if passed_count == total else 1


if __name__ == "__main__":
    sys.exit(main())
