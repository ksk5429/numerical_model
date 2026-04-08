---
name: Bug report
about: Report a reproducible defect in Op^3
title: "[BUG] "
labels: bug
assignees: ksk5429
---

## What happened

A clear, concise description of the unexpected behaviour.

## Reproduction

Minimal Python snippet or shell command that triggers the issue:

```python
from op3 import build_foundation, compose_tower_model
# ...
```

## Expected behaviour

What you thought should happen.

## Environment

- OS: (Windows 11, Ubuntu 24.04, macOS 14, ...)
- Python version: `python --version`
- Op^3 commit: `git rev-parse HEAD`
- OpenSeesPy version: `python -c "import openseespy; print(openseespy.__version__)"`
- OpenFAST binary version (if relevant): `OpenFAST.exe -v`

## V&V status

- [ ] `python tests/test_code_verification.py` passes
- [ ] `python tests/test_reproducibility.py` passes
- [ ] `python scripts/calibration_regression.py` passes

## Additional context

Logs, screenshots, paths to .out / .outb files, etc.
