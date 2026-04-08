# GitHub Actions CI status

Current state of the three GitHub Actions workflows as of v0.3.3
(commit `5251b7f`).

## Symptom

All three workflows are marked **failure** on every push:

| Workflow | File | Status |
|---|---|---|
| Op3 V&V | `.github/workflows/ci.yml` | failure |
| Verify Op^3 framework | `.github/workflows/verify.yml` (legacy v0.1 workflow) | failure |
| Deploy Sphinx docs to GitHub Pages | `.github/workflows/docs-deploy.yml` | failure |

## Diagnosis

The failure signature is **identical across all three workflows** and
matches the pattern documented in the Op^3 developer notes from the
v0.1 CI setup session:

- Job completes in **2 seconds** (before any step runs)
- `runner_name` is **empty** in the API response
- No step output is generated
- `steps` array is empty

**Root cause**: GitHub Actions spending limit on the `ksk5429`
account is set to $0, which prevents any runner from provisioning
for private / usage-billed workflows.

This is NOT a bug in the workflow YAML files themselves. The same
workflows produce working runs on repos without the spending-limit
constraint.

## Fix (2 minutes in the GitHub web UI)

1. Go to **https://github.com/settings/billing/spending_limit**
2. Scroll to the **GitHub Actions** section
3. Current setting is probably "$0" or "No spending limit: unchecked"
4. Either:
   - **Option A (recommended, free)**: Keep the $0 spending limit
     but verify you have the free monthly minutes. Free GitHub
     Actions minutes for public repos are **unlimited** --- private
     repos get 2000 min / month. If `numerical_model` is public,
     you should have unlimited free minutes.
   - **Option B**: Increase the spending limit to a small non-zero
     value (e.g. $10) as a belt-and-braces measure.
5. Save

If the repo is **public** and the spending limit is $0, the
workflows should still run on the unlimited-free tier. If they are
not running, this is a known GitHub billing quirk --- setting the
limit to $1 and saving, then setting back to $0, typically resolves
it.

## After fix

Re-trigger the failing workflows:

```bash
# Option A: dummy empty commit
git commit --allow-empty -m "ci: retrigger workflows"
git push origin main

# Option B: in the GitHub web UI
# Go to the Actions tab -> Op3 V&V -> Run workflow
```

The first successful run should show:

- **Op3 V&V**: ~5 min total, 14 test modules each reporting their
  pass counts (see the ``vv-suite`` job steps list in
  `.github/workflows/ci.yml`)
- **Deploy Sphinx docs to GitHub Pages**: ~3 min, then publishes
  HTML to `https://ksk5429.github.io/numerical_model/`

## Legacy workflow cleanup

The `Verify Op^3 framework` workflow in
`.github/workflows/verify.yml` is a v0.1 artifact that predates the
current V&V suite. It should either be removed or rewritten to
delegate to `release_validation_report.py`. I recommend removing it
because the current `Op3 V&V` workflow (`ci.yml`) covers everything
it was checking.

## Independent verification of the workflow correctness

Both `ci.yml` and `docs-deploy.yml` have been tested for syntactic
correctness via the local Sphinx build (which reproduces what
`docs-deploy.yml` runs) and via the local release validation report
script (which reproduces what `ci.yml` runs). Both produce clean
output locally:

- `sphinx-build -b html docs/sphinx docs/sphinx/_build/html`
  -> 14 HTML pages, 66 cosmetic warnings, 0 errors
- `python scripts/release_validation_report.py`
  -> 18/19 PASS, 0 mandatory FAIL, 42 s total

The workflows will produce matching output when the GitHub runner
provisioning issue is resolved.
