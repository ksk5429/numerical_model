# Contributing to Op³

Thanks for your interest in contributing to the Op³ framework. Op³
is developed as a research-grade framework supporting a PhD
dissertation and open scientific review, so contribution rules are
stricter than a typical open-source project.

**This file is the short version.** The authoritative contributor
guide lives at [`docs/sphinx/contributing.rst`](docs/sphinx/contributing.rst)
and is rendered in the Sphinx documentation.

## The one rule that matters

**Every code change ships with a test that would have failed before
the change.** No exceptions, even for bug fixes. See the full
explanation in the Sphinx contributing guide.

## Quick start for contributors

1. Fork and clone the repository.
2. Set up the environment:
   ```bash
   python -m venv .venv
   source .venv/Scripts/activate     # Windows Git Bash
   pip install -e ".[test,docs,dev]"
   ```
3. Bootstrap OpenFAST v5.0.0 binary and r-test:
   ```bash
   bash tools/openfast/install.sh
   mkdir -p tools/r-test_v5 && cd tools/r-test_v5
   git clone --depth=1 --branch v5.0.0 https://github.com/OpenFAST/r-test.git
   cd ../..
   ```
4. Run the full V&V sweep to confirm your environment works:
   ```bash
   PYTHONUTF8=1 python scripts/release_validation_report.py
   ```
   Expected: 18/19 PASS with 0 mandatory FAIL.

5. Create a feature branch from `main`:
   ```bash
   git checkout -b feat/my-feature
   ```

6. Make your change. Add a test. Run the V&V sweep again. Include
   the test output in your pull request description.

7. Use the pull request template at
   [`.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md).

## What the full contributor guide covers

- The V&V-or-it-didn't-happen rule with concrete examples
- The "never fabricate measured data" rule
- Commit discipline (no `git add -A`, no bulk staging, no amends)
- Commit message format (conventional commits)
- Branching model
- Step-by-step workflow for adding new turbines, standards, V&V tests
- Code style (PEP 8, type hints, docstrings, SI units)
- Running ruff / mypy / sphinx locally
- Review criteria
- Release process

Read the full guide at
https://github.com/ksk5429/numerical_model/blob/main/docs/sphinx/contributing.rst

## Contact

- Issues: https://github.com/ksk5429/numerical_model/issues
- Email: ksk5429@snu.ac.kr
