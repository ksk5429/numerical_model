"""
Release validation report generator (Phase 7 / Task 7.4 support).

Runs the entire Op^3 evidence base end-to-end and produces a single
consolidated JSON + Markdown validation report. The output is the
canonical artifact to attach to a GitHub release or submit alongside
a JOSS paper.

The report includes:

  1. Code verification (analytical cantilever references)
  2. Consistency + sensitivity invariants
  3. Extended V&V (2.7-2.20)
  4. PISA module, cyclic degradation, HSsmall
  5. Mode D dissipation-weighted
  6. OpenFAST runner infrastructure
  7. Backlog closure (2.10, 2.15, 2.16)
  8. UQ (MC propagation, PCE, Bayesian)
  9. Reproducibility snapshot
 10. Calibration regression against published references
 11. Three-analyses smoke (11 examples x 3 analyses)
 12. DNV-ST-0126 conformance audit
 13. IEC 61400-3 conformance scoping
 14. OC6 Phase II benchmark (AWAITING_VERIFY status)
 15. PISA cross-validation (AWAITING_VERIFY status)
 16. Solution verification (mesh + dt convergence)

Run:
    python scripts/release_validation_report.py

Output:
    validation/release_report/<version>_<timestamp>/
        report.json
        report.md
        individual test stdout captures
"""
from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class TestStage:
    name: str
    kind: str                      # 'test', 'script', 'audit'
    command: list[str]
    optional: bool = False
    status: str = "PENDING"
    wall_seconds: float = 0.0
    stdout_tail: list[str] = field(default_factory=list)


STAGES: list[TestStage] = [
    TestStage("code_verification", "test",
              ["python", "tests/test_code_verification.py"]),
    TestStage("consistency", "test",
              ["python", "tests/test_consistency.py"]),
    TestStage("sensitivity", "test",
              ["python", "tests/test_sensitivity.py"]),
    TestStage("extended_vv", "test",
              ["python", "tests/test_extended_vv.py"]),
    TestStage("pisa", "test", ["python", "tests/test_pisa.py"]),
    TestStage("cyclic_degradation", "test",
              ["python", "tests/test_cyclic_degradation.py"]),
    TestStage("hssmall", "test", ["python", "tests/test_hssmall.py"]),
    TestStage("mode_d", "test", ["python", "tests/test_mode_d.py"]),
    TestStage("openfast_runner", "test",
              ["python", "tests/test_openfast_runner.py"]),
    TestStage("backlog_closure", "test",
              ["python", "tests/test_backlog_closure.py"]),
    TestStage("uq", "test", ["python", "tests/test_uq.py"]),
    TestStage("reproducibility", "test",
              ["python", "tests/test_reproducibility.py"]),
    TestStage("calibration_regression", "script",
              ["python", "scripts/calibration_regression.py"]),
    TestStage("three_analyses", "script",
              ["python", "scripts/test_three_analyses.py"]),
    TestStage("dnv_st_0126", "audit",
              ["python", "scripts/dnv_st_0126_conformance.py", "--all"],
              optional=True),   # 1 known SiteA 1P resonance flag is expected
    TestStage("iec_61400_3", "audit",
              ["python", "scripts/iec_61400_3_conformance.py", "--all"],
              optional=True),
    TestStage("oc6_phase2", "audit",
              ["python", "scripts/oc6_phase2_benchmark.py"],
              optional=True),
    TestStage("pisa_cross_validation", "audit",
              ["python", "scripts/pisa_cross_validation.py"],
              optional=True),
    TestStage("solution_verification", "script",
              ["python", "scripts/solution_verification.py"]),
    # v0.4 dissertation reconciliation layer
    TestStage("ch7_bayesian_scour_real_mc", "script",
              ["python", "scripts/dissertation/ch7_site_a_bayesian_scour_real_mc.py"],
              optional=True),   # requires PHD root
    TestStage("ch6_cross_turbine", "script",
              ["python", "scripts/dissertation/ch6_cross_turbine_generalization.py"],
              optional=True),
]


def run_stage(stage: TestStage, workdir: Path) -> None:
    started = dt.datetime.now()
    env = {"PYTHONUTF8": "1", **__import__("os").environ}
    log_path = workdir / f"{stage.name}.log"
    try:
        proc = subprocess.run(
            stage.command, cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, env=env, timeout=600,
        )
        stdout = proc.stdout or ""
        rc = proc.returncode
    except subprocess.TimeoutExpired:
        stdout = "<TIMEOUT after 600 s>"
        rc = -1

    stage.wall_seconds = round((dt.datetime.now() - started).total_seconds(), 1)
    log_path.write_text(stdout, encoding="utf-8")
    # Keep the final 8 lines for the report
    stage.stdout_tail = [l for l in stdout.splitlines()[-8:] if l.strip()]
    if rc == 0:
        stage.status = "PASS"
    elif stage.optional:
        stage.status = f"OPTIONAL_FAIL (rc={rc})"
    else:
        stage.status = f"FAIL (rc={rc})"


def render_markdown(stages: list[TestStage], meta: dict) -> str:
    lines = [
        f"# Op^3 release validation report",
        "",
        f"- **Version**: {meta['version']}",
        f"- **Git commit**: `{meta['git_sha']}`",
        f"- **Git describe**: `{meta['git_describe']}`",
        f"- **Generated**: {meta['timestamp']}",
        f"- **Python**: {meta['python_version']}",
        "",
        "## Summary",
        "",
        f"- **{meta['n_pass']}** PASS",
        f"- **{meta['n_fail']}** FAIL (mandatory)",
        f"- **{meta['n_opt_fail']}** optional failures",
        f"- **{meta['n_total']}** stages total",
        f"- **{meta['total_wall']:.1f} s** total wall time",
        "",
        "## Stages",
        "",
        "| # | Stage | Kind | Status | Wall (s) | Tail |",
        "|---|---|---|---|---:|---|",
    ]
    for i, s in enumerate(stages, 1):
        tail = " / ".join(s.stdout_tail[-2:])[:80] if s.stdout_tail else ""
        tail = tail.replace("|", "\\|")
        lines.append(
            f"| {i} | `{s.name}` | {s.kind} | **{s.status}** | {s.wall_seconds} | `{tail}` |"
        )
    lines.extend([
        "",
        "## Provenance",
        "",
        f"- Repository root: `{REPO_ROOT}`",
        "- Every stage's full stdout is persisted alongside this report",
        "  as `<stage_name>.log`",
        "- This report is the canonical artifact for the v0.3.0 release",
        "  and is designed to be attached to the GitHub release or",
        "  submitted alongside a JOSS paper.",
        "",
    ])
    return "\n".join(lines)


def main():
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = REPO_ROOT / "validation/release_report" / f"v0.3.0_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Capture git metadata
    def _git(*args):
        try:
            return subprocess.check_output(["git"] + list(args),
                                           cwd=REPO_ROOT, text=True).strip()
        except Exception:
            return ""

    meta = {
        "version": "0.3.0",
        "timestamp": dt.datetime.now().isoformat(),
        "git_sha": _git("rev-parse", "HEAD"),
        "git_describe": _git("describe", "--tags", "--dirty"),
        "python_version": sys.version.split()[0],
    }

    print()
    print("=" * 78)
    print(f" Op3 release validation report -- v0.3.0")
    print("=" * 78)
    print(f"  commit : {meta['git_sha']}")
    print(f"  tag    : {meta['git_describe']}")
    print(f"  python : {meta['python_version']}")
    print(f"  output : {out_dir}")
    print()

    started_total = dt.datetime.now()
    for i, stage in enumerate(STAGES, 1):
        print(f"  [{i:>2}/{len(STAGES)}] {stage.name:<28} ...", end=" ", flush=True)
        run_stage(stage, out_dir)
        print(f"{stage.status:<16}  {stage.wall_seconds:>6.1f}s")

    total_wall = (dt.datetime.now() - started_total).total_seconds()
    n_pass = sum(1 for s in STAGES if s.status == "PASS")
    n_fail = sum(1 for s in STAGES if s.status.startswith("FAIL"))
    n_opt_fail = sum(1 for s in STAGES if s.status.startswith("OPTIONAL_FAIL"))
    meta.update({
        "n_pass": n_pass, "n_fail": n_fail, "n_opt_fail": n_opt_fail,
        "n_total": len(STAGES), "total_wall": total_wall,
    })

    # Write JSON + Markdown
    report = {"meta": meta, "stages": [asdict(s) for s in STAGES]}
    (out_dir / "report.json").write_text(json.dumps(report, indent=2),
                                          encoding="utf-8")
    (out_dir / "report.md").write_text(render_markdown(STAGES, meta),
                                        encoding="utf-8")

    print()
    print("=" * 78)
    print(f" {n_pass}/{len(STAGES)} PASS  |  {n_fail} FAIL  |  "
          f"{n_opt_fail} optional  |  {total_wall:.1f} s total")
    print(f" report: {out_dir}/report.md")
    print("=" * 78)
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
