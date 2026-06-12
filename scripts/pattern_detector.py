#!/usr/bin/env python3
"""Pattern Detector — automated response shape drift engine.

Reads logs/snapshots/*.jsonl and compares observed keys against the
learned shapes in api/tests/.qa_memory.json.

Outputs:
  - Console diff summary
  - logs/pending_regressions.json — changes awaiting approval/rejection

Usage:
  python scripts/pattern_detector.py                 # scan and report
  python scripts/pattern_detector.py --approve       # accept all pending changes
  python scripts/pattern_detector.py --reject        # discard all pending changes
  python scripts/pattern_detector.py --approve /api/settings  # approve one endpoint
"""

import argparse
import json
import sys
from collections import defaultdict, Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MEMORY_FILE = ROOT / "api" / "tests" / ".qa_memory.json"
SNAPSHOT_DIR = ROOT / "logs" / "snapshots"
PENDING_FILE = ROOT / "logs" / "pending_regressions.json"


def _load_memory() -> dict:
    if MEMORY_FILE.exists():
        return json.loads(MEMORY_FILE.read_text())
    return {"learned_shapes": {}}


def _load_snapshots() -> dict[str, list[set]]:
    """Read *.jsonl files; return {endpoint: [set_of_keys, ...]}."""
    result: dict[str, list] = defaultdict(list)
    if not SNAPSHOT_DIR.exists():
        return result
    for f in SNAPSHOT_DIR.glob("*.jsonl"):
        for line in f.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                result[entry["endpoint"]].append(set(entry["keys"]))
            except Exception:
                pass
    return result


def _dominant_shape(shapes: list[set]) -> set:
    """Return the key-set that appears most often (majority vote)."""
    if not shapes:
        return set()
    frozen = [frozenset(s) for s in shapes]
    most_common = Counter(frozen).most_common(1)[0][0]
    return set(most_common)


def detect(snapshots: dict, memory: dict) -> list[dict]:
    """Return list of drift findings."""
    learned = memory.get("learned_shapes", {})
    findings = []
    for endpoint, shapes in snapshots.items():
        if len(shapes) < 3:
            continue  # not enough data to be confident
        observed = _dominant_shape(shapes)
        if endpoint not in learned:
            findings.append({
                "type": "new_endpoint",
                "endpoint": endpoint,
                "observed_keys": sorted(observed),
                "learned_keys": [],
            })
        else:
            known = set(learned[endpoint].get("keys", []))
            lost = known - observed
            gained = observed - known
            if lost or gained:
                findings.append({
                    "type": "shape_drift",
                    "endpoint": endpoint,
                    "observed_keys": sorted(observed),
                    "learned_keys": sorted(known),
                    "lost": sorted(lost),
                    "gained": sorted(gained),
                })
    return findings


def _print_findings(findings: list[dict]) -> None:
    if not findings:
        print("✅  No drift detected — all observed shapes match learned shapes.")
        return
    print(f"⚠️  {len(findings)} drift finding(s):\n")
    for f in findings:
        ep = f["endpoint"]
        if f["type"] == "new_endpoint":
            print(f"  🆕  NEW  {ep}")
            print(f"       keys: {f['observed_keys']}")
        else:
            print(f"  ⚡  DRIFT  {ep}")
            if f["lost"]:
                print(f"       lost:   {f['lost']}")
            if f["gained"]:
                print(f"       gained: {f['gained']}")
        print()


def _save_pending(findings: list[dict]) -> None:
    PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
    PENDING_FILE.write_text(json.dumps({"pending": findings}, indent=2))
    print(f"📄  Pending regressions saved → {PENDING_FILE}")
    print("    Approve: python scripts/pattern_detector.py --approve")
    print("    Reject:  python scripts/pattern_detector.py --reject")


def _approve(memory: dict, endpoint: str | None) -> None:
    if not PENDING_FILE.exists():
        print("Nothing pending.")
        return
    pending = json.loads(PENDING_FILE.read_text()).get("pending", [])
    learned = memory.setdefault("learned_shapes", {})
    approved = []
    for f in pending:
        ep = f["endpoint"]
        if endpoint and ep != endpoint:
            continue
        learned[ep] = {"keys": f["observed_keys"]}
        approved.append(ep)
        print(f"  ✅  Approved shape for {ep}")
    MEMORY_FILE.write_text(json.dumps(memory, indent=2))
    remaining = [f for f in pending if f["endpoint"] not in approved]
    if remaining:
        PENDING_FILE.write_text(json.dumps({"pending": remaining}, indent=2))
    else:
        PENDING_FILE.unlink(missing_ok=True)
    print(f"Updated {MEMORY_FILE}")


def _reject(endpoint: str | None) -> None:
    if not PENDING_FILE.exists():
        print("Nothing pending.")
        return
    if endpoint:
        pending = json.loads(PENDING_FILE.read_text()).get("pending", [])
        remaining = [f for f in pending if f["endpoint"] != endpoint]
        PENDING_FILE.write_text(json.dumps({"pending": remaining}, indent=2))
        print(f"  ❌  Rejected {endpoint}")
    else:
        PENDING_FILE.unlink(missing_ok=True)
        print("  ❌  All pending regressions rejected (no memory update)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--approve", nargs="?", const=True,
                        metavar="ENDPOINT", help="Approve pending (all or one endpoint)")
    parser.add_argument("--reject", nargs="?", const=True,
                        metavar="ENDPOINT", help="Reject pending (all or one endpoint)")
    args = parser.parse_args()

    memory = _load_memory()

    if args.approve:
        ep = args.approve if isinstance(args.approve, str) else None
        _approve(memory, ep)
        return 0

    if args.reject:
        ep = args.reject if isinstance(args.reject, str) else None
        _reject(ep)
        return 0

    snapshots = _load_snapshots()
    if not snapshots:
        print("ℹ️  No snapshots found in", SNAPSHOT_DIR)
        print("   Set SNAPSHOT_DIR env var or run tests with snapshot middleware active.")
        return 0

    findings = detect(snapshots, memory)
    _print_findings(findings)
    if findings:
        _save_pending(findings)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
