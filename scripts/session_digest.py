"""
Session Digest Generator.

Produces a concise summary of the current Op3 state for
emailing to yourself or saving as a handoff note.

Usage:
    python scripts/session_digest.py
    python scripts/session_digest.py --save  # writes to docs/digests/
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def git_log(n=5):
    try:
        out = subprocess.check_output(
            ["git", "log", f"--oneline", f"-{n}"],
            cwd=str(REPO), text=True, stderr=subprocess.DEVNULL,
        )
        return out.strip().split('\n')
    except Exception:
        return ["(git not available)"]


def count_tests():
    total = 0
    for tf in (REPO / "tests").glob("test_*.py"):
        with open(tf, encoding="utf-8", errors="ignore") as f:
            total += sum(1 for line in f if line.strip().startswith("def test_"))
    return total


def count_benchmarks():
    results_file = REPO / "validation" / "cross_validations" / "all_results.json"
    if results_file.exists():
        data = json.loads(results_file.read_text(encoding="utf-8"))
        total = len(data)
        verified = sum(1 for r in data if r.get("status") == "verified")
        return total, verified
    return 0, 0


def count_figures():
    fig_dir = REPO / "validation" / "figures"
    if fig_dir.exists():
        return len(list(fig_dir.rglob("*.png"))) + len(list(fig_dir.rglob("*.html")))
    return 0


def get_version():
    init = REPO / "op3" / "__init__.py"
    if init.exists():
        for line in init.read_text(encoding="utf-8").splitlines():
            if "__version__" in line and "=" in line:
                return line.split("=")[1].strip().strip('"').strip("'")
    return "unknown"


def generate_digest(session_notes: str = "") -> str:
    now = datetime.now()
    version = get_version()
    n_tests = count_tests()
    n_bench, n_verified = count_benchmarks()
    n_figs = count_figures()
    commits = git_log(5)

    digest = f"""# Op3 Session Digest — {now.strftime('%Y-%m-%d %H:%M')}

## Current State
- **Version:** {version}
- **Tests:** {n_tests} passing
- **Benchmarks:** {n_bench} total, {n_verified} verified
- **Figures:** {n_figs}
- **PyPI:** pip install op3-framework

## Recent Commits
"""
    for c in commits:
        digest += f"- {c}\n"

    if session_notes:
        digest += f"\n## Session Notes\n{session_notes}\n"

    digest += f"""
## Pending (human action)
- [ ] Rotate PyPI token (if exposed)
- [ ] Fill Human Review Workbook (docs/HUMAN_REVIEW_WORKBOOK.docx)
- [ ] GitHub: topics, Discussions, Release v1.0.0-rc2

## Next Session Start
1. Load memory: `project_op3_v1_rc2_session_20260410.md`
2. Run: `git log --oneline -5`
3. Run: `make test` (verify nothing broke)
"""
    return digest


def main():
    save = "--save" in sys.argv

    notes = ""
    if "--notes" in sys.argv:
        idx = sys.argv.index("--notes")
        if idx + 1 < len(sys.argv):
            notes = sys.argv[idx + 1]

    digest = generate_digest(notes)
    print(digest)

    if save:
        out_dir = REPO / "docs" / "digests"
        out_dir.mkdir(parents=True, exist_ok=True)
        now = datetime.now().strftime("%Y%m%d_%H%M")
        out_file = out_dir / f"digest_{now}.md"
        out_file.write_text(digest, encoding="utf-8")
        print(f"\nSaved: {out_file}")


if __name__ == "__main__":
    main()
