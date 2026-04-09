Contributing guide
==================

Op\ :sup:`3` is developed as a research-grade framework that has to
survive a PhD defense, a journal review, and an industry
qualification. That imposes stricter contribution rules than a
typical open-source project. This guide is the complete contract for
anyone adding code, tests, documentation, or data.

.. contents:: Contents
   :local:
   :depth: 2

The V&V-or-it-didn't-happen rule
---------------------------------

**Every code change must ship with a test that would have failed
before the change.** This is the single most important rule in the
project. No exceptions.

* Fixing a bug? Write the test that exhibits the bug, confirm it
  fails, then write the fix, confirm it passes.
* Adding a feature? Write a test that asserts the feature behaves as
  designed, confirm it fails in a minimal-implementation build, then
  implement until the test passes.
* Refactoring? Run the full V&V suite before and after. The test
  deltas (pass counts, timings, reproducibility hash) must match
  except where an intentional numerical change is documented.

The PR template (``.github/PULL_REQUEST_TEMPLATE.md``) requires
pasting the V&V output of the full test run as evidence.

Never fabricate measured data
------------------------------

This is rule #2, documented in the project memory at
``feedback_session_2026_04_01_final.md``. If a reference number is
not in the cited paper or the cited dataset, mark it ``AWAITING_VERIFY``
and let the V&V harness flip status automatically when someone fills
it in. Never guess, never "interpolate from memory", never use a
placeholder that looks like a real number.

The PISA cross-validation harness
(``scripts/pisa_cross_validation.py``) is the reference
implementation of this pattern: each case has a citation, a status
flag, and a real paper-extracted reference that was only filled in
after the paper was actually opened.

Commit discipline
------------------

* **Never use** ``git add -A`` **or** ``git add .``. Always stage
  specific files. The project has hundreds of gitignored artifacts
  (binaries, logs, large data) and one accidental bulk-add can
  balloon the repo history.
* **Never bypass hooks** with ``--no-verify`` unless a maintainer has
  explicitly approved.
* **Never amend published commits.** If a hook failure kills a
  commit, fix the issue and make a NEW commit. The previous commit
  is untouched.
* **Never force-push** to ``main``. Feature branches can be force-
  pushed by the branch author before review; ``main`` is strictly
  append-only.

Commit message format
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

   <type>(<scope>): <short description>

   <body explaining the WHY, not the WHAT>

   Co-Authored-By: <co-author>

Types (conventional commits):

* ``feat`` -- new user-visible feature
* ``fix`` -- bug fix
* ``docs`` -- documentation only
* ``test`` -- adding or fixing tests
* ``refactor`` -- internal change with no behaviour difference
* ``perf`` -- performance improvement
* ``ci`` -- CI / release engineering
* ``chore`` -- dependency bumps, tooling updates

Scopes (project-specific):

* ``pisa``, ``cyclic``, ``hssmall``, ``mode-d`` -- soil modules
* ``uq``, ``openfast``, ``builder`` -- specific subsystems
* ``ci``, ``release``, ``deps`` -- infrastructure
* ``v0.3.1``, ``v0.3.2``, ... -- release tags

Example:

.. code-block:: text

   fix(pisa): depth functions + eccentric-load compliance

   Closes the v0.3.1 PISA finding by implementing the three physics
   corrections documented in DEVELOPER_NOTES section 13.2: ...

Branching model
---------------

* ``main`` -- always green, always releasable, all tags come from
  here
* ``feature/<name>`` -- feature branches off main
* ``fix/<issue-id>`` -- bug fix branches off main
* ``docs/<topic>`` -- documentation-only branches

Pull requests must target ``main`` and must pass the full CI workflow
before merge.

Adding a new turbine to the calibration regression
---------------------------------------------------

Opening an issue is the recommended first step (use the
``calibration_request`` issue template). The workflow is:

1. Add a new entry to
   ``op3/opensees_foundations/builder.py::TOWER_TEMPLATES``
   with the turbine geometry.
2. Add a new ``examples/<NN>_<turbine_name>/build.py`` composing the
   ``TowerModel``.
3. Add a new entry to
   ``scripts/calibration_regression.py::REFERENCES`` with the
   published reference frequency, tolerance, and citation.
4. Add the rotor 1P frequency to ``ROTOR_1P_HZ`` in
   ``scripts/dnv_st_0126_conformance.py``.
5. Update the example count in ``scripts/test_three_analyses.py`` if
   needed (the script auto-discovers examples).
6. Run the full V&V sweep and confirm the new example passes
   calibration and both conformance audits.
7. Update ``docs/DEVELOPER_NOTES.md`` section 2 with the new entry.
8. Commit with message ``feat(calibration): add <turbine> to
   regression catalog``.

Adding a new foundation standard
--------------------------------

1. Create ``op3/standards/<standard_name>.py`` implementing the
   stiffness function(s) with full NumPy docstrings, citing the
   source in the module docstring.
2. Add unit tests in ``tests/test_standards_<name>.py`` with at
   least:

   * Linearity in G (doubling G doubles K)
   * Symmetry and positive-definiteness of the output matrix
   * Agreement with a hand-computed reference at one point
3. Add an entry to the standards table in
   ``docs/sphinx/standards.rst``.
4. Add the standard name to the accepted-source list in
   ``scripts/iec_61400_3_conformance.py::check_I10_3_1_foundation_source``.
5. Commit with ``feat(standards): add <standard_name> module``.

Adding a new V&V test
---------------------

1. Create the test in ``tests/test_<topic>.py`` using the standalone
   runner pattern (``def main() -> int``) or pytest function pattern
   (``def test_xxx()``). Both work.
2. Add the test module to the stage list in
   ``scripts/release_validation_report.py::STAGES``.
3. Add the test to the CI workflow in
   ``.github/workflows/ci.yml`` (under ``vv-suite``).
4. Add a row to the test summary table in
   ``docs/sphinx/verification.rst``.
5. Run the full sweep and confirm the new test passes.

Code style
----------

* **PEP 8** with line length up to 100 characters (``ruff`` config
  in ``pyproject.toml``).
* **Type hints** on all public function signatures (``mypy`` config
  in ``pyproject.toml``).
* **Google or NumPy docstrings** with at least one ``Parameters``
  and ``Returns`` section.
* **CommonMark Markdown** for documentation. No HTML tags, no
  framework-specific extensions.
* **SI units** throughout public APIs (see
  :doc:`technical_reference` section 1).
* **f-strings** for string formatting, never ``%`` or ``.format()``.
* **Absolute imports** within the ``op3`` package
  (``from op3.foundations import ...``), not relative
  (``from .foundations import ...``).
* **Dataclasses** for structured data, not plain dicts.

Running the tools locally
-------------------------

.. code-block:: bash

   # Formatting + lint
   ruff check op3 scripts tests
   ruff format op3 scripts tests

   # Type check
   mypy op3

   # Full test suite
   PYTHONUTF8=1 python scripts/release_validation_report.py

   # Sphinx build
   sphinx-build -b html docs/sphinx docs/sphinx/_build/html -W --keep-going

   # Coverage
   pytest --cov=op3 --cov-report=term-missing

Documentation contributions
---------------------------

All public API additions must come with a matching docstring. The
Sphinx documentation picks docstrings up automatically via autodoc,
so you do not usually need to write separate RST. Exceptions:

* New foundation mode -- add a section to
  ``docs/sphinx/foundation_modes.rst``
* New standard -- add a row to
  ``docs/sphinx/standards.rst``
* New UQ tool -- add a section to ``docs/sphinx/uq.rst``
* New OpenFAST coupling surface -- add to
  ``docs/sphinx/openfast_coupling.rst``
* Mathematical derivation -- add to
  ``docs/sphinx/technical_reference.rst``
* End-to-end worked example -- add to
  ``docs/sphinx/user_manual.rst``

Review process
--------------

All PRs are reviewed by the project maintainer (Kim Kyeong Sun).
Review criteria:

1. **V&V evidence** attached to the PR description.
2. **Commit history** follows the discipline rules above.
3. **Code style** checks pass (``ruff``, ``mypy``).
4. **No fabricated data** -- every reference number has a citation.
5. **Documentation** updated where required.
6. **Reproducibility snapshot** intentionally updated (or unchanged).

Security
--------

* **Never commit secrets**, credentials, or API keys. Use environment
  variables or external secret managers.
* **Never commit the OpenFAST binary** (it is 44 MB and lives in
  ``.gitignore``).
* **Never commit the r-test clone** (it is 1.6 GB).
* **Never commit copyrighted paper PDFs** (``tools/papers/`` is
  gitignored).
* **Never commit patient / personal data** -- this is a wind turbine
  framework but the same discipline applies to the dissertation's
  SiteA field data.

Release process
---------------

Only the project maintainer tags releases. The release procedure is:

1. Run the full V&V sweep on a clean checkout:

   .. code-block:: bash

      python scripts/release_validation_report.py

2. Confirm 18/19 PASS with 0 mandatory FAIL (the DNV SiteA flag is
   expected optional).
3. Update ``CHANGELOG.md`` with the release entry.
4. Bump ``CITATION.cff`` version and date.
5. Bump ``pyproject.toml`` version.
6. Commit the release changes with message
   ``release: v<version> -- <summary>``.
7. Tag the commit with an annotated tag:

   .. code-block:: bash

      git tag -a v0.X.Y -m "Op^3 v0.X.Y -- <summary>"

8. Push ``main`` and the tag to origin.
9. Attach the release validation report Markdown to the GitHub
   release page.
10. If a DOI is desired, ensure Zenodo is linked to the repo and
    the release will auto-create a DOI.

Contact
-------

* Issues: https://github.com/ksk5429/numerical_model/issues
* Email: ksk5429@snu.ac.kr
* Dissertation project: https://github.com/ksk5429 (top pinned)
