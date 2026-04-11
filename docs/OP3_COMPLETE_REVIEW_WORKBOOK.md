# Op3 Complete Human Review Workbook

**Author:** Kyeong Sun Kim, Seoul National University
**Framework:** Op3 v1.0.0-rc2 (OptumGX–OpenSeesPy–OpenFAST)
**Date started:** _______________
**Date completed:** _______________

---

## How to Use This Workbook

This workbook combines all 7 human-AI interaction protocols into a single document. Work through it sequentially over 1-2 weeks. When finished, share the completed workbook with your AI assistant by saying:

> "I completed the Op3 Complete Review Workbook. Here are my responses."

The AI will then cross-check your answers, generate fix commits for any errors found, and update all REVIEW-STATUS tags from PENDING to VERIFIED.

**Total estimated time:** 8-12 hours across multiple sittings

---

# Section 1: Formula Verification

**Estimated time:** 3-4 hours
**What you need:** The 4 source papers open alongside the code files

## 1.1 PISA Sand Coefficients

**Code file:** `op3/standards/pisa.py` lines 83-107
**Paper:** Byrne et al. (2020) "PISA Design Model for Monopiles for Offshore Wind Turbines: Application to a Stiff Glacial Clay Till" — wait, is this the sand or clay paper?

**First task:** Determine which paper is which. Write the correct mapping:

- Byrne et al. (2020) covers: [ ] Sand (Dunkirk) [ ] Clay (Cowden)
- Burd et al. (2020) covers: [ ] Sand (Dunkirk) [ ] Clay (Cowden)

**AI flag:** The code comments at lines 66-70 may have these swapped. Your answer here determines whether the comments need fixing.

**Now verify each coefficient against the SAND paper:**

| Component | Parameter | Code Value | Paper Table & Row | Paper Value | Match? |
|-----------|-----------|-----------|-------------------|-------------|--------|
| lateral_p | k_1 | 8.64 | Table ___, Row ___ | | [ ] Y [ ] N |
| lateral_p | k_2 | -0.81 | | | [ ] Y [ ] N |
| lateral_p | n_1 | 0.966 | | | [ ] Y [ ] N |
| lateral_p | n_2 | 0.914 | | | [ ] Y [ ] N |
| lateral_p | x_u | 64.78 | | | [ ] Y [ ] N |
| lateral_p | k_u | 20.86 | | | [ ] Y [ ] N |
| moment_m | k_1 | 18.1 | | | [ ] Y [ ] N |
| moment_m | k_2 | 0.0 | | | [ ] Y [ ] N |
| moment_m | n_1 | 0.0 | | | [ ] Y [ ] N |
| base_shear | k_1 | 3.28 | | | [ ] Y [ ] N |
| base_shear | k_2 | -0.37 | | | [ ] Y [ ] N |
| base_moment | k_1 | 0.30 | | | [ ] Y [ ] N |
| base_moment | k_2 | 0.0 | | | [ ] Y [ ] N |

Notes on any mismatches:
```
[Write here]
```

## 1.2 PISA Clay Coefficients

**Code file:** `op3/standards/pisa.py` lines 110-144
**Paper:** The CLAY paper (which one did you determine above?)

| Component | Parameter | Code Value | Paper Table & Row | Paper Value | Match? |
|-----------|-----------|-----------|-------------------|-------------|--------|
| lateral_p | k_1 | 10.60 | | | [ ] Y [ ] N |
| lateral_p | k_2 | -1.55 | | | [ ] Y [ ] N |
| lateral_p | n_1 | 0.822 | | | [ ] Y [ ] N |
| lateral_p | n_2 | 0.018 | | | [ ] Y [ ] N |
| lateral_p | x_u | 89.57 | | | [ ] Y [ ] N |
| lateral_p | k_u | 13.27 | | | [ ] Y [ ] N |
| moment_m | k_1 | 3.22 | | | [ ] Y [ ] N |
| moment_m | k_2 | 0.32 | | | [ ] Y [ ] N |
| base_shear | k_1 | 2.18 | | | [ ] Y [ ] N |
| base_shear | k_2 | -0.27 | | | [ ] Y [ ] N |
| base_moment | k_1 | 0.30 | | | [ ] Y [ ] N |
| base_moment | k_2 | 0.04 | | | [ ] Y [ ] N |

Notes:
```
[Write here]
```

## 1.3 Gazetas (1991) Embedment Factors

**Code file:** `op3/standards/api_rp_2geo.py` lines 46-51 and 88-93
**Paper:** Gazetas (1991) "Formulas and charts for impedances of surface and embedded foundations" J. Geotech. Eng. 117(9)

| Formula | Code | Paper Eq/Table | Paper Value | Match? |
|---------|------|----------------|-------------|--------|
| K_xx embed factor | `1.0 + 0.55*(D/R)^0.85` | | | [ ] Y [ ] N |
| K_zz embed factor | `1.0 + 0.54*D/R` | | | [ ] Y [ ] N |
| K_rxx embed factor | `1.0 + 2.3*D/(2R)` | | | [ ] Y [ ] N |
| K_rxx cubic term | `+ 0.58*(D/(2R))^3` | | | [ ] Y [ ] N |
| K_rzz embed factor | `1.0 + 1.6*D/(2R)` | | | [ ] Y [ ] N |
| Coupling K_xrx | `D*(1/3)*K_x_0*eta_x` | | | [ ] Y [ ] N |

**CRITICAL CHECK:** Does `api_rp_2geo.py` line 48 (the `api_pile_stiffness` function) include or exclude the cubic term `0.58*(L/D)^3` for K_rxx?

- [ ] Includes it
- [ ] Missing it (BUG — needs fix)
- [ ] The original paper doesn't have it

Compare with `dnv_st_0126.py` line 242 which HAS the cubic term. Are they computing the same formula?

Notes:
```
[Write here]
```

## 1.4 Efthymiou & Gazetas (2018) Suction Caisson

**Code file:** `op3/optumgx_interface/step2_gazetas_stiffness.py` lines 41-73
**Paper:** Efthymiou & Gazetas (2018) "Elastic Stiffnesses of a Rigid Suction Caisson" J. Geotech. Geoenviron. Eng. 145(2)

| Stiffness | Code correction factors | Paper Eq # | Paper formula | Match? |
|-----------|------------------------|-----------|---------------|--------|
| Kv | `(1+0.4*L/R)*(1+1.6*R/H)*(1+(0.9-0.25*L/R)*L/(H-L))` | | | [ ] Y [ ] N |
| Kh | `(1+1.1*L/R)*(1+1.15*L/H)^0.65*(1+0.7*R/H)` | | | [ ] Y [ ] N |
| Kr | `(1+L/R)^1.4*(1+0.15*R/H)*(1+0.95*L/R)` | | | [ ] Y [ ] N |
| Khr | `0.6*Kh*L` | | | [ ] Y [ ] N |

Does the paper use R (radius) or D (diameter)? Does the code match?

Notes:
```
[Write here]
```

## 1.5 Houlsby & Byrne (2005) OWA

**Code file:** `op3/standards/owa_bearing.py` lines 72-80
**Paper:** Houlsby & Byrne (2005) "Design procedures for installation of suction caissons in clay" Proc ICE Geotech Eng 158(2)

The lateral stiffness base factor in the code is `4*G*R/(1-nu)`.

**Question:** The standard Gazetas LATERAL formula is `8*G*R/(2-nu)`. Houlsby & Byrne use a different base. Is `4*G*R/(1-nu)` what their paper actually says?

- [ ] Yes, this is Houlsby & Byrne Eq. ___
- [ ] No, their paper says _______________
- [ ] Cannot determine (equation not in this paper)

Notes:
```
[Write here]
```

---

# Section 2: Sign Convention Audit

**Estimated time:** 30 minutes
**What you need:** A structural dynamics textbook (e.g., Chopra, or DNV-RP)

## 2.1 Coupling Term Signs

Open both files side by side:
- `op3/standards/api_rp_2geo.py` lines 106-109
- `op3/standards/pisa.py` lines 383-384

| Term | api_rp_2geo.py | pisa.py | Your expected sign |
|------|---------------|---------|-------------------|
| K[0,4] (x force → ry rotation) | [ ] + [ ] - | [ ] + [ ] - | [ ] + [ ] - |
| K[4,0] (ry rotation → x force) | [ ] + [ ] - | [ ] + [ ] - | [ ] + [ ] - |
| K[1,3] (y force → rx rotation) | [ ] + [ ] - | [ ] + [ ] - | [ ] + [ ] - |
| K[3,1] (rx rotation → y force) | [ ] + [ ] - | [ ] + [ ] - | [ ] + [ ] - |

**Physical reasoning:** When you push a pile head in +x direction, does the mudline rotation about y-axis have a + or - sign in your coordinate system?

Your answer:
```
[Write here — this determines which module is correct]
```

**Decision needed:** Which convention should Op3 standardize on?

- [ ] PISA convention (K[0,4] negative, K[1,3] positive)
- [ ] Gazetas convention (all positive)
- [ ] Other: _______________

---

# Section 3: Cross-Validation Integrity

**Estimated time:** 45 minutes
**What you need:** `validation/cross_validations/run_all_cross_validations.py` open

## 3.1 Live vs Hardcoded Classification

For each benchmark, open the function in the runner and determine if it actually executes Op3 code or returns a pre-baked number.

**How to check:** Search for `from op3 import` or `model.eigen()` (= live) vs `op3_value=6.006` or a bare number assignment (= hardcoded).

| # | Benchmark | Live? | Evidence (line # or function call) |
|---|-----------|-------|------------------------------------|
| 1 | OC3 eigenvalue | [ ] Live [ ] Hardcoded | |
| 3 | IEA 15MW eigenvalue | [ ] Live [ ] Hardcoded | |
| 5 | Centrifuge 22-case | [ ] Live [ ] Hardcoded | |
| 8 | Houlsby VH | [ ] Live [ ] Hardcoded | |
| 14 | Fu & Bienen NcV | [ ] Live [ ] Hardcoded | |
| 15 | Vulpe NcV/NcH/NcM | [ ] Live [ ] Hardcoded | |
| 16 | Jalbi KL/KR | [ ] Live [ ] Hardcoded | |
| 17 | Gazetas KH/KR | [ ] Live [ ] Hardcoded | |
| 19 | Bothkennar Kr | [ ] Live [ ] Hardcoded | |
| 22 | DJ Kim My | [ ] Live [ ] Hardcoded | |
| 24 | Seo f1 | [ ] Live [ ] Hardcoded | |
| 28 | Jeong cyclic | [ ] Live [ ] Hardcoded | |

## 3.2 Regression Safety Question

**If you change the Gazetas K_rxx formula (fixing the missing cubic term), which benchmarks would automatically detect the change?**

List the benchmark numbers that would fail: _______________

**If the answer is "none" or "only #1-3", that's the honest answer for your committee.** The hardcoded benchmarks prove the code ONCE produced correct answers but don't detect regressions.

## 3.3 OptumGX Reproducibility

The OptumGX results (NcV=6.006, NcH=3.847, NcM=1.468) were computed during a single session on 2026-04-10 using the OptumGX GUI.

| Question | Answer |
|----------|--------|
| Can a reviewer without OptumGX reproduce these? | [ ] Yes [ ] No |
| Are the OptumGX scripts committed? | [ ] Yes [ ] No |
| Are mesh parameters documented (element count, adaptivity)? | [ ] Yes [ ] No |
| Is the geometry (D, L, su) clearly stated? | [ ] Yes [ ] No |
| Could someone use a different FE code (e.g., Plaxis, Abaqus) to verify? | [ ] Yes [ ] No |

---

# Section 4: Unit Consistency

**Estimated time:** 30 minutes

## 4.1 SoilState Convention

**File:** `op3/standards/pisa.py` line 217

The docstring says `su_or_phi: float` with units `[Pa]` for clay.

| Call site | File:line | Value passed | Is this Pa? |
|-----------|----------|-------------|-------------|
| test_pisa.py | :46 | 80.0e3 | [ ] Yes (80 kPa) [ ] No |
| test_pisa.py | :47 | 120.0e3 | [ ] Yes (120 kPa) [ ] No |
| test_foundations.py | :178 | 50.0 | [ ] Yes (0.05 kPa) [ ] No |
| test_foundations.py | :179 | 100.0 | [ ] Yes (0.1 kPa) [ ] No |
| pisa_demo_oc3.py | varies | ___ | [ ] Yes [ ] No |
| README.md example | :43 | ___ | [ ] Yes [ ] No |

**Is test_foundations.py:178 a bug?** (50 Pa = 0.05 kPa is essentially zero strength)

- [ ] Yes, should be 50e3 (50 kPa = 50000 Pa)
- [ ] No, the docstring is wrong (should say kPa)
- [ ] Doesn't matter because the test only checks > 0

Your recommendation:
```
[Write here]
```

## 4.2 Magic Numbers

For each number, trace it to its source and write the citation.

| Number | File:line | Physical meaning | Source (paper/chapter/table) |
|--------|----------|-----------------|----------------------------|
| 10000.0 | OpenSeesPy_v4:249 | | |
| 0.059 | run_all_cross:227 | | |
| 39.18 | run_all_cross:748 | | |
| 0.60 | run_remaining_gaps | | |
| 2.5 | OpenSeesPy_v6:40 | | |
| 0.2433 | OpenSeesPy_v6:46 | | |
| 0.67 | optumgx_vhm_full:27 | | |
| 20.0 | optumgx_vhm_full:27 | | |

---

# Section 5: Decision Log Review

**Estimated time:** 30 minutes
**File:** `docs/DECISION_LOG.md`

## 5.1 Decision Completeness

Read each decision entry. For each one, answer:

| Decision | Do you agree? | Would you decide differently? | Missing context? |
|----------|--------------|------------------------------|-----------------|
| DL-001: 4-tier mode hierarchy | [ ] Agree [ ] Disagree | | |
| DL-002: Efthymiou as primary | [ ] Agree [ ] Disagree | | |
| DL-003: FELA for clay only | [ ] Agree [ ] Disagree | | |
| DL-004: Power law scour | [ ] Agree [ ] Disagree | | |
| DL-005: 0.60 mobilisation | [ ] Agree [ ] Disagree | | |
| DL-006: Power law cyclic | [ ] Agree [ ] Disagree | | |
| DL-007: PyPI name | [ ] Agree [ ] Disagree | | |
| DL-008: Apache-2.0 | [ ] Agree [ ] Disagree | | |

## 5.2 Missing Decisions

Are there technical choices that were made but NOT recorded in the Decision Log?

List any you can think of:
```
[Write here]
```

---

# Section 6: Pre-Flight Checklist Practice

**Estimated time:** 15 minutes

## 6.1 Fill Out a Sample Checklist

Pick a task you plan to do next (e.g., "add HSsmall visualization" or "fix the Gazetas cubic term"). Fill out the pre-flight checklist from `docs/PREFLIGHT_CHECKLIST.md`:

**Task:** _______________________________________________

**Inputs available:**
- [ ] _______________
- [ ] _______________

**Assumptions:**
- Physics: _______________
- Units: _______________
- Valid L/D range: _______________

**Verification plan:** _______________

**Go / No-Go:** [ ] GO [ ] STOP — missing: _______________

---

# Section 7: Authorship Declaration

**Estimated time:** 45 minutes
**Purpose:** Prepare your defense answers

## 7.1 Role Attribution

For each category, write ONE sentence describing what YOU (the human) contributed vs what the AI contributed.

| Category | AI did | You did |
|----------|--------|---------|
| Framework architecture (4-mode hierarchy) | | |
| Formula selection (which stiffness model) | | |
| Coefficient verification (checking paper values) | | |
| OptumGX analysis (running limit analysis) | | |
| Cross-validation design (choosing benchmarks) | | |
| Visualization (34 figures) | | |
| Dissertation chapters (Ch 1-9) | | |
| Field data interpretation (OMA, RANSAC) | | |
| Centrifuge testing (22 cases) | | |
| Decision-making (DL-001 through DL-008) | | |

## 7.2 Committee Q&A Rehearsal

Write your answer to each question. Practice saying them out loud.

**Q1: "How much of this code was written by AI?"**
```
[Your answer — 2-3 sentences]
```

**Q2: "How do you know the formulas are correct?"**
```
[Your answer — reference the workbook, benchmarks, paper checks]
```

**Q3: "Can the results be reproduced?"**
```
[Your answer — distinguish live vs hardcoded vs OptumGX-dependent]
```

**Q4: "What if the PISA coefficients are wrong?"**
```
[Your answer — what's the blast radius? which tests catch it?]
```

**Q5: "Did you verify the OptumGX results independently?"**
```
[Your answer — how? against which published references?]
```

**Q6: "What is the novel contribution — is it the AI's work or yours?"**
```
[Your answer — Mode D dissipation weighting, spatial age concept, etc.]
```

**Q7: "If the AI made an error in a formula, how would you catch it?"**
```
[Your answer — regression tests, red team tests, workbook verification]
```

## 7.3 Provenance Awareness

For each figure category, write what type of data it uses:

| Figure | Data source | Category |
|--------|------------|----------|
| VHM failure envelope | | [ ] COMPUTED [ ] OPTUMGX [ ] PUBLISHED [ ] SYNTHETIC |
| Cross-pipeline composite | | [ ] COMPUTED [ ] OPTUMGX [ ] PUBLISHED [ ] SYNTHETIC |
| Campbell diagram | | [ ] COMPUTED [ ] OPTUMGX [ ] PUBLISHED [ ] SYNTHETIC |
| 3D bucket pressure | | [ ] COMPUTED [ ] OPTUMGX [ ] PUBLISHED [ ] SYNTHETIC |
| Rainflow heatmap | | [ ] COMPUTED [ ] OPTUMGX [ ] PUBLISHED [ ] SYNTHETIC |
| Sequential Bayesian | | [ ] COMPUTED [ ] OPTUMGX [ ] PUBLISHED [ ] SYNTHETIC |
| MC histogram | | [ ] COMPUTED [ ] OPTUMGX [ ] PUBLISHED [ ] SYNTHETIC |

---

# Section 8: Red Team Self-Test

**Estimated time:** 30 minutes
**Purpose:** Think like an adversary

## 8.1 Break Your Own Code

Run the red team tests: `python -m pytest tests/test_red_team.py -v`

Do all 35 tests pass? [ ] Yes [ ] No

If any fail, which ones and why?
```
[Write here]
```

## 8.2 Think of New Edge Cases

Write 3 edge cases that the current red team tests do NOT cover:

1. _______________________________________________
2. _______________________________________________
3. _______________________________________________

## 8.3 Regression Gate Check

Run: `python -m pytest tests/test_regression.py -v`

Do all 25 tests pass? [ ] Yes [ ] No

Now intentionally change one coefficient in `pisa.py` (e.g., change `k_1: 8.64` to `k_1: 9.00`) and re-run. Does the regression test catch it?

- [ ] Yes, test ___ failed
- [ ] No, no test caught it (this is a gap!)

**Restore the original value after testing.**

---

# Section 9: Session Digest Test

**Estimated time:** 5 minutes

Run: `python scripts/session_digest.py`

Does the output look correct?

| Field | Value shown | Correct? |
|-------|-----------|----------|
| Version | | [ ] Y [ ] N |
| Test count | | [ ] Y [ ] N |
| Benchmark count | | [ ] Y [ ] N |
| Figure count | | [ ] Y [ ] N |
| Recent commits | | [ ] Y [ ] N |

---

# Completion Checklist

Mark each section when done:

- [ ] Section 1: Formula Verification (all tables filled)
- [ ] Section 2: Sign Convention (decision made)
- [ ] Section 3: Cross-Validation (live/hardcoded classified)
- [ ] Section 4: Unit Consistency (all magic numbers sourced)
- [ ] Section 5: Decision Log (all 8 entries reviewed)
- [ ] Section 6: Pre-Flight Checklist (sample filled)
- [ ] Section 7: Authorship (all Q&A written)
- [ ] Section 8: Red Team (tests run, 3 new cases written)
- [ ] Section 9: Session Digest (verified)

**Signature:** ___________________________ **Date:** _______________

---

*When complete, share this workbook with your AI assistant. The AI will cross-check every answer, fix confirmed errors, update REVIEW-STATUS tags, and generate a verification report.*
