# Op^3 v1.0.0 Release Notes

**Release date:** 2026-04-16
**Prior release:** 1.0.0-rc2 (2026-04-10)
**Tag:** `v1.0.0`

## What this release is

This is the first stable release of the Op^3 integrated numerical framework for
offshore wind turbine foundation assessment. The release is cut from the
same codebase as `1.0.0-rc2` with no functional changes; it is a stable
version tag to support the pending submission of the framework paper to
*Advances in Engineering Software* (paper J10 in the KSK publication roster)
and to provide a reproducible citation for papers J2, J5, J6, J8, and J9
that depend on the framework.

## What is in the release

Same substance as 1.0.0-rc2:

- **OptumGX three-dimensional limit analysis** integration with automated
  parameter extraction for four foundation modes (A fixed, B six-by-six
  stiffness, C distributed BNWF, D dissipation-weighted generalised BNWF).
- **OpenSeesPy structural dynamics** integration with eigenvalue sweep,
  pushover analysis, and cyclic degradation.
- **OpenFAST v5 aero-servo-hydro-elastic** coupling via SoilDyn mode with
  six-by-six stiffness handoff.
- **Fatigue module** per DNV-RP-C203 with rainflow counting.
- **Op^3 Studio web application** with eight-tab interactive UI, large-
  language-model chat sandbox, and Three.js three-dimensional visualisation.
- **Mooring anchor module** with novel dissipation-centroid padeye method
  and one hundred thirty-four validation tests.
- **Thirty-nine cross-validation benchmarks** from twenty-five-plus published
  sources at ninety-two percent coverage.

## Verification

Test suite at the release tag:

- 362 passed, 11 skipped (optional data not bundled in this checkout).
- Zero failures after the 2026-04-16 cp949 encoding fix in
  `tests/test_op3_framework.py::TestSSOTConfig::test_yaml_exists_and_parses`
  (explicit `encoding="utf-8"` added).

## Installation

```bash
pip install op3-framework==1.0.0
```

or directly from this release on GitHub:

```bash
pip install https://github.com/ksk5429/numerical_model/releases/download/v1.0.0/op3_framework-1.0.0-py3-none-any.whl
```

## Citing

```
@software{op3_2026,
  author  = {Kim, Kyeong Sun},
  title   = {Op^3: OptumGX-OpenSeesPy-OpenFAST integrated numerical
             modeling framework for offshore wind turbines},
  version = {1.0.0},
  date    = {2026-04-16},
  doi     = {10.5281/zenodo.19476542},
  url     = {https://github.com/ksk5429/numerical_model}
}
```

## Changes versus 1.0.0-rc2

- Version string bumped to `1.0.0` in `op3/__init__.py`,
  `pyproject.toml`, `CITATION.cff`, and `docs/sphinx/conf.py`.
- `__release_date__` attribute added to `op3/__init__.py`.
- Pre-existing Windows cp949 encoding bug in
  `tests/test_op3_framework.py::TestSSOTConfig::test_yaml_exists_and_parses`
  fixed by specifying `encoding="utf-8"` when reading the YAML that
  contains Korean site metadata.

No library behaviour changes. Papers J2, J5, J6, J8, and J9 that cite
the framework can use `1.0.0` as a pinned version.

## Known limitations carried from 1.0.0-rc2

- Scour mode validated on Gunsan normally consolidated clay only;
  applicability boundaries to other soil classes are discussed in
  the companion OE-D-26-00984 paper.
- Anchor mode validated on one hundred thirty-four reference tests;
  field validation is open.
- OpenFAST coupling is tested against NREL reference turbines;
  utility-scale commercial OWT turbines are not yet validated.
- Op^3 Studio is a research prototype, not production-hardened.

## Manual publish steps (pending after local build)

The following steps require user credentials and cannot be completed
automatically. They are listed for user action.

1. **Rotate the PyPI token** (pending manual task #1 in memory). The
   previous token was exposed in conversation and should be revoked at
   <https://pypi.org/manage/account/token/>. Generate a new token scoped
   to `op3-framework` and store it in `~/.pypirc` or the environment
   variable `TWINE_PASSWORD`.

2. **Upload wheel and source distribution to PyPI.**

   ```bash
   cd F:/GITHUB3/numerical_model_fresh
   python -m twine upload dist/op3_framework-1.0.0*
   ```

3. **Create the Git tag and push.**

   ```bash
   cd F:/GITHUB3/numerical_model_fresh
   git add -A
   git commit -m "release: v1.0.0"
   git tag -a v1.0.0 -m "Op^3 v1.0.0 stable release"
   git push origin main --tags
   ```

4. **Create the GitHub release.** Either in the web UI at
   <https://github.com/ksk5429/numerical_model/releases/new?tag=v1.0.0>
   or via the `gh` CLI:

   ```bash
   gh release create v1.0.0 dist/op3_framework-1.0.0-py3-none-any.whl \
     dist/op3_framework-1.0.0.tar.gz \
     --title "Op^3 v1.0.0" \
     --notes-file RELEASE_NOTES_v1.0.0.md
   ```

5. **Zenodo mint.** Zenodo automatically mints a DOI for the GitHub
   release if the repository has the Zenodo integration enabled. Verify
   at <https://zenodo.org/account/settings/github/> that the repository
   is switched on. The concept DOI `10.5281/zenodo.19476542` stays
   constant; a new version DOI is assigned to this release.

6. **Update README badge.** After PyPI upload succeeds, the README
   version badge should automatically reflect `1.0.0`. Verify manually.

## What does not happen in this release

- No breaking API changes.
- No dependency changes.
- No new tests or benchmarks (the test suite remains at 362 passing).
- No new documentation pages; the Sphinx content is identical to rc2.
