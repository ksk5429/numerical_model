"""
Dissertation analysis entry points for Chapter 6, 7, 8.

This package is the Op^3 side of the dissertation SSOT reconciliation:
the actual analysis scripts for Chapters 6/7/8 live in the PhD
working directory at ``F:/TREE_OF_THOUGHT/PHD/code/``, but they are
invoked from Op^3 via the shim modules below. This means:

* the dissertation build reads its numerics from the same committed
  code path that the Op^3 framework exports
* reviewers can reproduce every Ch 6-8 numerical claim by running
  scripts/dissertation/*.py from the Op^3 checkout, which in turn
  imports the PHD analysis code
* no duplicate authority: the PHD scripts remain the single home for
  dissertation-specific logic, while the Op^3 infrastructure (data
  loaders, UQ, calibration regression, OpenFAST coupling) is imported
  into them

See op3/data_sources.py for the PHD path resolver and CONTRIBUTING
for the reconciliation plan.
"""
