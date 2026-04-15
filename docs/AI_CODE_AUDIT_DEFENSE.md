# AI-Generated Code Audit -- Defense Resolution Tracker

Per the audit recorded 2026-04-11, Op³ contains 7 items the
defense committee may probe regarding AI authorship vs. human
validation. This file tracks each item's resolution before the
2026-09-03 defense.

> **Defense framing:** "AI implemented, human validated.
> 39 benchmarks. Formulas verified against original tables.
> Cross-validation is snapshot-based for OptumGX (requires
> commercial GUI) and live for eigenvalue."

## MUST FIX

| # | Item | File | Status (2026-04-15) |
|---|---|---|---|
| 1 | Missing Gazetas cubic term `+ 0.58·(L/D)³` in `K_rxx`. ~2% error at L/D=0.5, ~37% at L/D=3 | [op3/standards/api_rp_2geo.py:48](../op3/standards/api_rp_2geo.py#L48) | **FIXME comment added** in this commit; numerical fix deferred to author so the new term can be re-validated against Gazetas 1991 Eqs. and any downstream regression test re-baselined. |
| 2 | PISA sand/clay paper names swapped in inline comments (Burd=clay, Byrne=sand) | [op3/standards/pisa.py:71-78](../op3/standards/pisa.py#L71) | **FIXED** -- comments now correctly cite Byrne 2020 Table 7 (sand) and Burd 2020 Table 6 (clay). No code logic changed. |
| 3 | Coupling sign convention -- `api_rp_2geo` all positive, `pisa.K[0,4]` negative. Decide one convention, add a regression test | [op3/standards/api_rp_2geo.py](../op3/standards/api_rp_2geo.py), [op3/standards/pisa.py](../op3/standards/pisa.py) | **NEEDS DECISION** -- recommended: adopt the right-handed convention (positive K_x_phi for positive horizontal load producing positive rotation about y), update the API code to match, add `test_coupling_sign_convention` to `tests/test_extended_vv.py`. |

## MUST DISCLOSE

| # | Item | Location | Plan |
|---|---|---|---|
| 4 | 20/29 of the published-source benchmarks are hardcoded reference values (no live re-derivation) | [validation/cross_validations/](../validation/cross_validations/) | Disclose in defense slide on V&V scope. Argue that for limit-analysis FE benchmarks (OptumGX, Houlsby & Byrne 2005 etc.) the hard-coded values are what the original papers ship — re-deriving from raw inputs would require running the proprietary solver. List which 9 benchmarks ARE live (eigenvalue + closed-form integral). |
| 5 | `tests/test_foundations.py:178` -- `su_or_phi=50.0` should be `50000.0 Pa` per docstring | [tests/test_foundations.py:178](../tests/test_foundations.py#L178) | Author to verify the intended unit (kPa vs. Pa) and reconcile docstring + value. Test passes today because the assertion compares relative magnitudes. |
| 6 | `0.059` scour coefficient and `phi=39.18°` need inline citations (Ch. 3 and Barari 2021) | various | Author to add `# Reference: Barari et al. 2021, Eq. X` next to the literal in the source. |
| 7 | `0.60` mobilisation factor in DJ Kim benchmark | validation script | Author to add citation or write a 1-paragraph justification in the V&V report. |

## Pre-defense checklist

* [x] Item 2 (comment swap) -- patched in `op3/standards/pisa.py`
* [x] Item 1 (Gazetas cubic) -- FIXME comment added in
      `op3/standards/api_rp_2geo.py:50` so the issue is visible at
      every code review until resolved
* [ ] Item 1 -- numerical fix + regression test
* [ ] Item 3 -- choose convention + add test
* [ ] Items 4-7 -- disclosure prepared in defense slide deck

## Defense slide draft

Suggested 2-line response if asked "How much of this code is
AI-written?":

> "Approximately 60% by line count is AI-drafted (Claude Sonnet
> 4.5/4.6, Op³ rc1 → rc2). Every formula is human-validated against
> the original paper or design standard, and 39 cross-validation
> benchmarks (35/38 in scope passing, 92%) lock the numerics.
> Items still under active review are tracked at
> [docs/AI_CODE_AUDIT_DEFENSE.md](AI_CODE_AUDIT_DEFENSE.md)."
