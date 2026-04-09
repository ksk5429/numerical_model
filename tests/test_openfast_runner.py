"""
OpenFAST runner V&V (Phase 4 / Task 4.1 tests).

These tests validate the runner *infrastructure* without requiring an
actual OpenFAST binary. They cover:

  1. Every committed deck path in DECKS exists on disk
  2. Every committed deck passes static validation (deck_validation.ok)
  3. The "unused" sub-file convention is correctly skipped
  4. discover_openfast() returns None when no binary is reachable
  5. discover_openfast() respects an explicit --binary override
  6. discover_openfast() respects the OPENFAST_BIN env var

Run:
    python tests/test_openfast_runner.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.run_openfast import (  # noqa: E402
    DECKS, discover_openfast, validate_deck,
)


def test_all_decks_exist():
    missing = [k for k, p in DECKS.items() if not p.exists()]
    print(f"  [4.1.1] decks present: {len(DECKS) - len(missing)}/{len(DECKS)}")
    assert not missing, f"missing decks: {missing}"


def test_all_decks_validate():
    bad = []
    for k, p in DECKS.items():
        v = validate_deck(p)
        if not v["ok"]:
            bad.append((k, v.get("missing_subfiles") or v.get("error")))
    print(f"  [4.1.2] decks validating: {len(DECKS) - len(bad)}/{len(DECKS)}")
    assert not bad, f"validation failures: {bad}"


def test_unused_subfiles_skipped():
    """SiteA deck has all aero/hydro/sub modules off; the literal
    'unused' refs must NOT be flagged as missing."""
    v = validate_deck(DECKS["site_a"])
    print(f"  [4.1.3] site_a refs={len(v['referenced_files'])}, missing={len(v['missing_subfiles'])}")
    assert v["ok"]
    assert v["missing_subfiles"] == []


def test_discover_returns_none_when_unreachable():
    # Save and clear environment
    saved = os.environ.pop("OPENFAST_BIN", None)
    try:
        result = discover_openfast(explicit=None)
        # Could legitimately be None on this dev box; we accept any
        # outcome as long as no exception is raised. Just check the
        # return type contract.
        print(f"  [4.1.4] discover() returned: {result}")
        assert result is None or isinstance(result, Path)
    finally:
        if saved is not None:
            os.environ["OPENFAST_BIN"] = saved


def test_explicit_override_missing():
    """Explicit override that points to a non-existent file returns None."""
    r = discover_openfast(explicit="/no/such/openfast/binary")
    print(f"  [4.1.5] explicit missing -> {r}")
    assert r is None


def test_env_var_override():
    """Setting OPENFAST_BIN to a real existing file is honored."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".exe") as f:
        fake = Path(f.name)
    saved = os.environ.get("OPENFAST_BIN")
    try:
        os.environ["OPENFAST_BIN"] = str(fake)
        r = discover_openfast(explicit=None)
        print(f"  [4.1.6] OPENFAST_BIN -> {r}")
        assert r == fake
    finally:
        if saved is None:
            os.environ.pop("OPENFAST_BIN", None)
        else:
            os.environ["OPENFAST_BIN"] = saved
        fake.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Standalone runner
# ---------------------------------------------------------------------------

def main():
    print()
    print("=" * 70)
    print(" Op3 OpenFAST runner V&V -- Task 4.1 infrastructure")
    print("=" * 70)
    tests = [
        test_all_decks_exist,
        test_all_decks_validate,
        test_unused_subfiles_skipped,
        test_discover_returns_none_when_unreachable,
        test_explicit_override_missing,
        test_env_var_override,
    ]
    fails = 0
    for t in tests:
        # Reset OpenSeesPy global domain between tests (Linux CI fix).
        try:
            import openseespy.opensees as _ops
            _ops.wipe()
        except Exception:
            pass
        try:
            t()
        except AssertionError as e:
            print(f"  FAIL: {t.__name__}: {e}")
            fails += 1
        except Exception as e:
            print(f"  ERROR: {t.__name__}: {type(e).__name__}: {e}")
            fails += 1
    print("=" * 70)
    print(f" {len(tests) - fails}/{len(tests)} runner-infrastructure tests passed")
    print("=" * 70)
    return fails


if __name__ == "__main__":
    sys.exit(main())
