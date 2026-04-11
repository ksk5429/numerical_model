# Op3 Decision Log

Technical decisions with rationale. Updated each session.
Format: ID, date, what was decided, what alternatives existed, why this choice, evidence, who decided.

---

## DL-001: Foundation mode hierarchy (A/B/C/D)
- **Date:** 2025-12 (initial design)
- **Decision:** 4-tier hierarchy: Fixed → 6x6 → BNWF → Dissipation-weighted
- **Alternatives:** Single mode (BNWF only), 2-tier (fixed + springs)
- **Why:** Progressive fidelity matches engineering workflow. Mode A for sanity checks, Mode B for code-compliant design, Mode C for site-specific, Mode D for post-yield assessment. Each mode validates the one below it.
- **Evidence:** Validated across 39 benchmarks (0.8-29% error range)
- **Decided by:** Human (KSK) — architectural decision

## DL-002: Efthymiou & Gazetas (2018) as primary stiffness formulation
- **Date:** 2026-04-10
- **Decision:** Use Efthymiou & Gazetas (2018) for Mode B suction caisson stiffness
- **Alternatives:** Gazetas (1991) surface+embed, Houlsby & Byrne (2005) OWA, Doherty (2005) 3D FE, Jalbi (2018) Plaxis regression
- **Why:** +3-10% vs Doherty 3D FE at L/D=0.5 (best among analytical). Gazetas 1991 underestimates KR by 56%. OWA overestimates KL by 38%.
- **Evidence:** `validation/cross_validations/field_oxcaisson_results.json`, benchmark #20
- **Decided by:** Human (KSK) after AI-generated comparison of 4 methods

## DL-003: OptumGX FELA for capacity, not sand displacement capacity
- **Date:** 2026-04-10
- **Decision:** Use OptumGX limit analysis for undrained clay capacity (NcV, NcH, NcM). Do NOT use it for drained sand horizontal capacity.
- **Alternatives:** Use FELA for both clay and sand
- **Why:** FELA computes theoretical plastic collapse. For Tresca clay this matches published values to 0.8-7.8%. For Mohr-Coulomb sand, FELA gives 1228 MN vs Achmus reference 45 MN — plastic collapse ≠ displacement-based capacity.
- **Evidence:** Benchmarks #14-15 (verified), #18 (out of calibration at +2628%)
- **Decided by:** Human (KSK) based on AI-generated comparison

## DL-004: Power law for scour-frequency sensitivity
- **Date:** 2026-04-10
- **Decision:** Use centrifuge-calibrated power law `df/f0 = 0.059 * (S/D)^1.5` for scour sensitivity
- **Alternatives:** Zaaijer (2006) analytical SSI, Prendergast (2015) lab model, Cheng (2024) FE
- **Why:** Calibrated to 22 centrifuge cases (mean error 1.19%). Prendergast range (5-10%) validates Op3 prediction (5.9%). Zaaijer's 0.8% is for piles, not suction buckets.
- **Evidence:** Benchmarks #10, #11, #26; Ch.3 Table 3.4
- **Decided by:** Human (KSK) — empirical fit to own centrifuge data

## DL-005: DJ Kim analytical capacity (0.60 mobilisation factor)
- **Date:** 2026-04-10
- **Decision:** Tripod yield moment My = 0.60 × Vu × lever_arm
- **Alternatives:** Full nonlinear BNWF pushover, elastic stiffness × theta_yield
- **Why:** Elastic approach overpredicts by 40x (parallel-axis term dominates). Nonlinear BNWF requires full SSOT structural data (not available for DJ Kim geometry). Analytical capacity with 60% mobilisation gives -0.7% error.
- **Evidence:** Benchmark #22 (My=92.4 vs ref 93.0 MNm)
- **Source of 0.60:** Typical yield mobilisation for suction buckets in sand at 0.6 deg rotation. Consistent with Barari (2021) back-analysis showing initial nonlinearity at ~60% of ultimate capacity.
- **Decided by:** AI proposed, human accepted based on physical reasoning

## DL-006: Jeong cyclic accumulation via power law, not FE cyclic
- **Date:** 2026-04-10
- **Decision:** Fit power law `theta = 0.033 * N^0.085` to Jeong (2021) data, do not simulate cycles in OpenSeesPy
- **Alternatives:** Run 100 cycles in OpenSeesPy with PySimple1 hysteresis
- **Why:** PySimple1 cyclic behavior is not calibrated to suction bucket test data. The power law fit gives +4.2% error at N=100. Running OpenSeesPy cycles would require uncertain calibration parameters and risk producing a number with false precision.
- **Evidence:** Benchmark #28 (N=100: +4.2%, N=1M: +3.6%)
- **Key insight:** Tripod b=0.085 vs monopile b=0.31 (LeBlanc 2010) — tripods accumulate rotation 4x slower
- **Decided by:** AI proposed, human accepted

## DL-007: PyPI package name `op3-framework`
- **Date:** 2026-04-10
- **Decision:** Publish as `op3-framework` not `op3` on PyPI
- **Alternatives:** `op3`, `op3-wind`, `optumgx-openseespy-openfast`
- **Why:** `op3` is a 3-character name likely to conflict. `op3-framework` is descriptive and available.
- **Decided by:** AI proposed, human accepted

## DL-008: Apache-2.0 license
- **Date:** 2026-04-10
- **Decision:** Apache-2.0 (not MIT)
- **Alternatives:** MIT, GPL-3.0, BSD-3-Clause
- **Why:** Apache-2.0 provides patent protection and is the same license as OpenFAST. MIT was in the LICENSE file by mistake; pyproject.toml and CITATION.cff always said Apache-2.0.
- **Decided by:** Human (KSK) — MIT was a template artifact
