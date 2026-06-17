"""Workflow Sensor — checks ruff, detect-secrets, test counts, and CI gate health."""
from __future__ import annotations
import subprocess
import time
from pathlib import Path

from .base import Severity, SensorReport

_MIN_TEST_COUNT = 90  # session-start gate requires 95 passing
_API_TEST_DIR = Path(__file__).parent.parent.parent / "api" / "tests"


def _run(cmd: list[str], cwd: Path | None = None) -> tuple[int, str]:
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return r.returncode, (r.stdout + r.stderr).strip()


def run() -> SensorReport:
    report = SensorReport("workflow")
    t0 = time.time()

    # 1. Ruff lint gate
    code, out = _run(["ruff", "check", "api/"], cwd=Path(__file__).parent.parent.parent)
    if code == 0:
        report.add("ruff", Severity.OK, "ruff check passed — no lint errors")
    else:
        errors = [l for l in out.splitlines() if "error" in l.lower() or l.strip().startswith("api/")]
        report.add("ruff", Severity.CRITICAL, f"ruff check failed ({len(errors)} issues)",
                   detail="\n".join(errors[:20]),
                   fix_hint="Run: ruff check --fix api/ — then commit the fixes")

    # 2. detect-secrets gate
    code, out = _run(["detect-secrets", "scan", "api/"], cwd=Path(__file__).parent.parent.parent)
    try:
        import json
        result = json.loads(out)
        secrets = [f for f in result.get("results", {}).values() if f]
        if secrets:
            report.add("secrets", Severity.CRITICAL,
                       f"detect-secrets found {len(secrets)} potential secrets",
                       detail=str(secrets[:3]),
                       fix_hint="Add '# pragma: allowlist secret' to test fixtures, or remove real credentials")
        else:
            report.add("secrets", Severity.OK, "detect-secrets scan clean")
    except Exception:
        report.add("secrets", Severity.WARN, "detect-secrets output not parseable", detail=out[:200])

    # 3. Test file count
    test_files = list(_API_TEST_DIR.glob("test_*.py"))
    report.add("test_files", Severity.OK if len(test_files) >= 10 else Severity.WARN,
               f"{len(test_files)} test files found in api/tests/")

    # 4. QA suite gate (dry run — count only, no execution)
    qa_files = ["api/tests/test_qa_suite.py", "api/tests/test_qa_intelligent.py"]
    for f in qa_files:
        if Path(f).exists():
            report.add("qa_gate", Severity.OK, f"{f} exists")
        else:
            report.add("qa_gate", Severity.CRITICAL, f"{f} missing — session-start gate broken",
                       fix_hint=f"Restore {f} from git history")

    # 5. CLAUDE.md presence (branch rules)
    claude_md = Path(__file__).parent.parent.parent / "CLAUDE.md"
    if claude_md.exists():
        content = claude_md.read_text()
        if "claude/zealous-carson-oMr43" in content:
            report.add("branch", Severity.OK, "CLAUDE.md specifies correct dev branch")
        else:
            report.add("branch", Severity.WARN, "CLAUDE.md branch reference may be stale",
                       fix_hint="Update branch name in CLAUDE.md")
    else:
        report.add("branch", Severity.CRITICAL, "CLAUDE.md missing",
                   fix_hint="Restore CLAUDE.md — it contains critical project rules")

    report.duration_ms = (time.time() - t0) * 1000
    return report
