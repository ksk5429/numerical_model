"""
End-to-end OpenFAST runner (Phase 4 / Task 4.1).

Runs an OpenFAST v4.0.2 simulation on any committed example deck and
captures the time-series .out file. The runner is binary-agnostic:
it discovers ``openfast.exe`` via (1) the ``OPENFAST_BIN`` environment
variable, (2) common Windows install paths, (3) the user PATH. If no
binary is found, the runner *still* validates the deck via the
existing parser pipeline so the failure mode is clear: deck is OK but
no executor is available.

Usage
-----
    python scripts/run_openfast.py site_a
    python scripts/run_openfast.py oc3 --tmax 10
    python scripts/run_openfast.py site_a --binary "C:\\openfast\\openfast_x64.exe"

Output
------
    validation/openfast_runs/<deck>_<timestamp>/
        run_log.txt
        SiteA-Ref4MW.out          (only if binary present)
        run_metadata.json

Exit codes
----------
    0  simulation ran to completion
    1  binary missing (deck is valid)
    2  deck parse error (need to fix the .fst before running)
    3  binary present but simulation failed
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


# ---------------------------------------------------------------------------
# Deck registry
# ---------------------------------------------------------------------------

DECKS = {
    "site_a": REPO_ROOT / "site_a_ref4mw/openfast_deck/SiteA-Ref4MW.fst",
    "oc3":    REPO_ROOT / "nrel_reference/openfast_rtest/5MW_OC3Mnpl_DLL_WTurb_WavesIrr/5MW_OC3Mnpl_DLL_WTurb_WavesIrr.fst",
    "oc4":    REPO_ROOT / "nrel_reference/oc4_jacket/5MW_OC4Jckt_DLL_WTurb_WavesIrr_MGrowth.fst",
    "iea15_monopile": REPO_ROOT / "nrel_reference/iea_15mw/OpenFAST_monopile/IEA-15-240-RWT-Monopile.fst",
    "iea15_volturnus": REPO_ROOT / "nrel_reference/iea_15mw/OpenFAST_volturnus/IEA-15-240-RWT-UMaineSemi.fst",
}


# ---------------------------------------------------------------------------
# Binary discovery
# ---------------------------------------------------------------------------

CANDIDATE_PATHS = [
    # Prefer v5+ (OpenFAST.exe) over v4 (openfast_x64.exe) so that the
    # current v5 r-test deck format is parsed correctly.
    str(REPO_ROOT / "tools/openfast/OpenFAST.exe"),
    str(REPO_ROOT / "tools/openfast/openfast_x64.exe"),
    r"C:\openfast\openfast_x64.exe",
    r"C:\openfast\bin\openfast_x64.exe",
    r"C:\Program Files\OpenFAST\openfast_x64.exe",
    r"C:\Program Files\OpenFAST\bin\openfast.exe",
    r"C:\OpenFAST-v4.0.2\openfast_x64.exe",
    "/usr/local/bin/openfast",
    "/usr/bin/openfast",
]


def discover_openfast(explicit: str | None = None) -> Path | None:
    """Locate the openfast binary; return None if not found."""
    if explicit:
        p = Path(explicit)
        return p if p.exists() else None
    env = os.environ.get("OPENFAST_BIN")
    if env and Path(env).exists():
        return Path(env)
    on_path = shutil.which("openfast") or shutil.which("openfast_x64")
    if on_path:
        return Path(on_path)
    for cand in CANDIDATE_PATHS:
        p = Path(cand)
        if p.exists():
            return p
    return None


# ---------------------------------------------------------------------------
# Deck validation (reuses verify_nrel_models parser primitives)
# ---------------------------------------------------------------------------

def validate_deck(fst_path: Path) -> dict:
    """Static validation: parse .fst, resolve sub-files, extract key params."""
    from scripts.verify_nrel_models import parse_fst_flags

    if not fst_path.exists():
        return {"ok": False, "error": f"deck not found: {fst_path}"}

    info = parse_fst_flags(fst_path)
    flags = info.get("flags", {})
    refs = info.get("referenced_files", {})

    # Check that every referenced sub-file exists
    missing = []
    for key, ref in refs.items():
        # OpenFAST stores "unused" (case-insensitive) for sub-files of
        # disabled modules; skip those.
        if not ref or ref.strip().lower() in ("unused", "none"):
            continue
        cand = (fst_path.parent / ref).resolve()
        if cand.exists():
            continue
        # Fallback: search by basename under fst.parent and its
        # grandparent (handles _shared_* directory rename quirks).
        basename = Path(ref).name
        found = False
        for root in [fst_path.parent, fst_path.parent.parent]:
            if not root.exists():
                continue
            hits = list(root.rglob(basename))
            if hits:
                found = True
                break
        if not found:
            missing.append((key, ref))

    return {
        "ok": len(missing) == 0,
        "deck": str(fst_path),
        "flags": flags,
        "referenced_files": refs,
        "missing_subfiles": missing,
    }


# ---------------------------------------------------------------------------
# Run record
# ---------------------------------------------------------------------------

@dataclass
class RunRecord:
    deck: str
    fst_path: str
    binary: str | None
    started_at: str
    ended_at: str | None
    return_code: int | None
    stdout_lines: int
    stderr_lines: int
    out_file: str | None
    out_file_kb: float | None
    deck_validation: dict
    notes: str = ""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("deck", choices=list(DECKS.keys()),
                    help="Which committed deck to run")
    ap.add_argument("--binary", default=None,
                    help="Path to openfast binary (overrides PATH discovery)")
    ap.add_argument("--tmax", type=float, default=None,
                    help="Override simulation TMax (seconds)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Validate deck and resolve binary, but do not run")
    args = ap.parse_args()

    fst = DECKS[args.deck]
    print()
    print("=" * 78)
    print(" Op3 OpenFAST runner -- Phase 4 / Task 4.1")
    print("=" * 78)
    print(f"  deck   : {args.deck}")
    print(f"  fst    : {fst}")

    val = validate_deck(fst)
    if not val["ok"]:
        print(f"  STATUS : DECK INVALID")
        if "error" in val:
            print(f"  error  : {val['error']}")
        for key, ref in val.get("missing_subfiles", []):
            print(f"  MISSING: {key} -> {ref}")
        return 2

    print(f"  modules: {[k for k, v in val['flags'].items() if k.startswith('Comp') and v not in ('0','')]}")
    print(f"  refs   : {len(val['referenced_files'])} sub-files, all present")

    binary = discover_openfast(args.binary)
    if binary is None:
        print(f"  STATUS : BINARY MISSING")
        print()
        print("  OpenFAST executable was not found. Tried:")
        if args.binary: print(f"    --binary  : {args.binary}")
        print(f"    OPENFAST_BIN env: {os.environ.get('OPENFAST_BIN', '<unset>')}")
        print(f"    PATH (openfast / openfast_x64)")
        for c in CANDIDATE_PATHS:
            print(f"    {c}")
        print()
        print("  To install OpenFAST v4.0.2:")
        print("    1. Download from https://github.com/OpenFAST/openfast/releases/tag/v4.0.2")
        print("    2. Either set OPENFAST_BIN=C:\\path\\to\\openfast_x64.exe")
        print("       or place the binary on PATH.")
        print()
        print("  Deck validation: PASS")
        print("  Runner is ready; only the executor is missing.")
        return 1

    print(f"  binary : {binary}")

    if args.dry_run:
        print("  STATUS : DRY-RUN OK (deck valid, binary located)")
        return 0

    # Set up output workspace
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = REPO_ROOT / "validation/openfast_runs" / f"{args.deck}_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"  workdir: {out_dir}")

    # Note: OpenFAST writes outputs into the same directory as the .fst.
    # We do NOT copy the deck to avoid breaking relative TwrFile/BldFile
    # paths. Instead the runner just changes cwd to fst.parent and
    # captures the OpenFAST stdout/stderr to the out_dir.
    # OpenFAST v4 has no -tmax CLI flag; if the user requested an
    # override, write a temporary deck with the new TMax line.
    fst_to_run = fst
    tmp_deck = None
    if args.tmax is not None:
        import re
        text = fst.read_text(errors="replace")
        new_text = re.sub(
            r"^(\s*)([-\d.Ee+]+)(\s+TMax\b)",
            rf"\g<1>{args.tmax}\g<3>",
            text,
            count=1,
            flags=re.MULTILINE,
        )
        tmp_deck = fst.with_name(fst.stem + "__tmax_override.fst")
        tmp_deck.write_text(new_text, encoding="utf-8")
        fst_to_run = tmp_deck
    cmd = [str(binary), str(fst_to_run.name)]

    started = dt.datetime.now().isoformat()
    log_path = out_dir / "run_log.txt"
    with log_path.open("w", encoding="utf-8") as log:
        log.write(f"# OpenFAST run log\ncommand: {' '.join(cmd)}\nstarted: {started}\n\n")
        log.flush()
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(fst.parent),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=3600,
            )
            log.write("===== STDOUT =====\n")
            log.write(proc.stdout)
            log.write("\n===== STDERR =====\n")
            log.write(proc.stderr)
            rc = proc.returncode
            stdout_lines = proc.stdout.count("\n")
            stderr_lines = proc.stderr.count("\n")
        except subprocess.TimeoutExpired:
            rc = -1
            stdout_lines = stderr_lines = 0
            log.write("\n===== TIMEOUT after 3600 s =====\n")

    ended = dt.datetime.now().isoformat()
    if tmp_deck is not None and tmp_deck.exists():
        try:
            tmp_deck.unlink()
        except Exception:
            pass

    # Locate any .out file emitted next to the .fst
    out_file = None
    out_kb = None
    stem = fst_to_run.stem
    for cand in fst.parent.glob(f"{stem}*.out"):
        out_file = str(cand)
        out_kb = round(cand.stat().st_size / 1024.0, 1)
        try:
            shutil.copy2(cand, out_dir / cand.name)
        except Exception:
            pass
        break

    record = RunRecord(
        deck=args.deck,
        fst_path=str(fst),
        binary=str(binary),
        started_at=started,
        ended_at=ended,
        return_code=rc,
        stdout_lines=stdout_lines,
        stderr_lines=stderr_lines,
        out_file=out_file,
        out_file_kb=out_kb,
        deck_validation=val,
        notes=f"tmax={args.tmax}" if args.tmax else "",
    )
    (out_dir / "run_metadata.json").write_text(
        json.dumps(asdict(record), indent=2, default=str), encoding="utf-8")

    print(f"  rc     : {rc}")
    if out_file:
        print(f"  output : {out_file} ({out_kb} kB)")
    print(f"  log    : {log_path}")

    if rc == 0:
        print("  STATUS : SIMULATION COMPLETE")
        return 0
    print("  STATUS : SIMULATION FAILED (see run_log.txt)")
    return 3


if __name__ == "__main__":
    sys.exit(main())
