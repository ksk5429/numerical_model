# Pull request

## Summary

What this PR does, in 1-3 sentences.

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] V&V test addition
- [ ] Documentation
- [ ] Infrastructure / CI

## V&V evidence

Paste the local test outputs (do **not** skip this section -- the
project policy is V&V-or-it-didn't-happen):

```
$ python tests/test_code_verification.py     # 4/4
$ python tests/test_pisa.py                   # 9/9
$ python tests/test_uq.py                     # 13/13
$ python tests/test_reproducibility.py        # REPRODUCIBLE
$ python scripts/calibration_regression.py    # 4/4
```

## Snapshot drift

If `tests/test_reproducibility.py` reports drift on any canonical
output, paste the diff and explain why the change is intentional. Bump
`tests/reproducibility_snapshot.json` only after a maintainer review.

## Checklist

- [ ] All V&V tests pass locally
- [ ] No fabricated reference values (use `AWAITING_VERIFY` for pending)
- [ ] New code has matching test in `tests/`
- [ ] Public API change has matching docstring + Sphinx update
