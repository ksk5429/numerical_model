# Op3 Human Review Workbook

**Purpose:** This workbook ensures that a human domain expert has independently verified every critical element of the Op3 framework before defense or publication. It is designed as a structured exercise: the human fills in each section, then the AI reviews the responses for completeness.

**How to use:**
1. Print this document or open it alongside the referenced source files
2. For each item, physically open the cited paper and verify the number
3. Write your verification notes in the "Human Response" field
4. Mark each item VERIFIED, FLAGGED, or NOT APPLICABLE
5. When complete, share this document with your AI assistant for a cross-check

**Time estimate:** 4-6 hours for a thorough review

---

## Part 1: Formula Verification (Open the paper, check the number)

### 1.1 PISA Calibration Coefficients

**File:** `op3/standards/pisa.py` lines 83-144

**Task:** Open Byrne et al. (2020) Table 7 and Burd et al. (2020) Table 6. For each coefficient below, write the value from the paper next to the code value.

| Component | Parameter | Code Value | Paper Value | Match? |
|-----------|-----------|-----------|-------------|--------|
| Sand lateral_p | k_1 | 8.64 | ___ | [ ] |
| Sand lateral_p | k_2 | -0.81 | ___ | [ ] |
| Sand lateral_p | n_1 | 0.966 | ___ | [ ] |
| Sand moment_m | k_1 | 18.1 | ___ | [ ] |
| Sand base_shear | k_1 | 3.28 | ___ | [ ] |
| Sand base_shear | k_2 | -0.37 | ___ | [ ] |
| Clay lateral_p | k_1 | 10.60 | ___ | [ ] |
| Clay lateral_p | k_2 | -1.55 | ___ | [ ] |
| Clay moment_m | k_1 | 3.22 | ___ | [ ] |
| Clay base_shear | k_1 | 2.18 | ___ | [ ] |
| Clay base_moment | k_1 | 0.30 | ___ | [ ] |

**Tip:** The PISA papers use different notation. Byrne 2020 Table 7 calls these "conic function parameters." Match by component name (lateral, moment, base_H, base_M) not by table column.

**Source paper for sand:** _________________________________
**Source paper for clay:** _________________________________

**AI flag:** The comments in the code swap the paper names. Line 66 says "Byrne 2020" for sand but line 70 says "Burd 2020" for sand. Which is correct?

Human Response:
```
[Write your verification notes here]
```

---

### 1.2 Gazetas Embedment Factors

**File:** `op3/standards/api_rp_2geo.py` lines 46-51, 88-93

**Task:** Open Gazetas (1991) "Formulas and charts for impedances of surface and embedded foundations" Table 3 or Eqs. 14-17. Verify each factor.

| Term | Code Formula | Paper Formula | Match? |
|------|-------------|--------------|--------|
| K_xx embed | `1.0 + 0.55 * (D/R)^0.85` | ___ | [ ] |
| K_zz embed | `1.0 + 0.54 * D/R` | ___ | [ ] |
| K_rxx embed | `1.0 + 2.3 * D/(2R)` | ___ | [ ] |
| K_rzz embed | `1.0 + 1.6 * D/(2R)` | ___ | [ ] |

**AI flag (CRITICAL):** The K_rxx formula in `api_rp_2geo.py:48` is:
```
(1.0 + 2.3 * L / D)
```
But `dnv_st_0126.py:242` has:
```
(1.0 + 2.3 * L / D + 0.58 * (L / D) ** 3)
```

Is the cubic term `0.58*(L/D)^3` present in the original Gazetas paper? Which version is correct?

Human Response:
```
[Write your verification notes here]
```

---

### 1.3 Efthymiou & Gazetas (2018) Suction Caisson

**File:** `op3/optumgx_interface/step2_gazetas_stiffness.py` lines 41-73

**Task:** Open Efthymiou & Gazetas (2018) "Elastic Stiffnesses of a Rigid Suction Caisson" Eqs. 8-14. Verify:

| Stiffness | Code correction factors | Paper equation | Match? |
|-----------|------------------------|----------------|--------|
| Kv | `(1 + 0.4*L/R) * (1 + 1.6*R/H) * ...` | ___ | [ ] |
| Kh | `(1 + 1.1*L/R) * (1 + 1.15*L/H)^0.65 * ...` | ___ | [ ] |
| Kr | `(1 + L/R)^1.4 * (1 + 0.15*R/H) * (1 + 0.95*L/R)` | ___ | [ ] |
| Khr | `0.6 * Kh * L` | ___ | [ ] |

**Tip:** The paper uses R (radius), not D (diameter). Check that the code uses R consistently.

Human Response:
```
[Write your verification notes here]
```

---

### 1.4 Houlsby & Byrne (2005) OWA Caisson

**File:** `op3/standards/owa_bearing.py` lines 72-80

**Task:** Open Houlsby & Byrne (2005) "Design procedures for installation of suction caissons" Eqs. 5.2-5.5.

**AI flag:** The lateral stiffness base factor is `4GR/(1-nu)` which is the Gazetas VERTICAL formula. Houlsby & Byrne use a different formulation than Gazetas for caisson lateral stiffness. Is this intentional and correct per Houlsby's paper?

Human Response:
```
[Write your verification notes here]
```

---

## Part 2: Sign Convention Audit

### 2.1 Coupling Term Sign

**Files to compare:**
- `op3/standards/api_rp_2geo.py` lines 106-109
- `op3/standards/pisa.py` lines 383-384

**Task:** The 6x6 stiffness matrix has off-diagonal coupling terms K[0,4] and K[1,3] that relate lateral force to rocking and vice versa.

Write the sign of each term in each module:

| Term | api_rp_2geo.py | pisa.py | Which is standard? |
|------|---------------|---------|-------------------|
| K[0,4] | ___ (+/-) | ___ (+/-) | ___ |
| K[4,0] | ___ (+/-) | ___ (+/-) | ___ |
| K[1,3] | ___ (+/-) | ___ (+/-) | ___ |
| K[3,1] | ___ (+/-) | ___ (+/-) | ___ |

**Tip:** The standard structural mechanics convention is that positive lateral force at the pile head (pushing in +x) induces a negative rotation about the y-axis if the reference point is at the mudline. Therefore K[0,4] should be negative for the standard convention.

**Question:** Does the Op3 builder (`builder.py:594`) use the PISA or Gazetas convention when constructing the OpenSeesPy model?

Human Response:
```
[Write your verification notes here]
```

---

## Part 3: Cross-Validation Integrity

### 3.1 Live vs Hardcoded Benchmarks

**File:** `validation/cross_validations/run_all_cross_validations.py`

**Task:** For each benchmark, check whether it actually runs Op3 code or returns a pre-baked number.

| # | Benchmark | Runs Op3? | How did you verify? |
|---|-----------|----------|-------------------|
| 1 | OC3 eigenvalue | [ ] Yes [ ] No | ___ |
| 5 | Centrifuge 22-case | [ ] Yes [ ] No | ___ |
| 8 | Houlsby VH envelope | [ ] Yes [ ] No | ___ |
| 14 | Fu & Bienen NcV | [ ] Yes [ ] No | ___ |
| 15 | Vulpe VHM | [ ] Yes [ ] No | ___ |
| 17 | Gazetas stiffness | [ ] Yes [ ] No | ___ |
| 22 | DJ Kim My | [ ] Yes [ ] No | ___ |
| 28 | Jeong cyclic | [ ] Yes [ ] No | ___ |

**Question:** If you change a formula in `pisa.py`, which benchmarks would FAIL automatically and which would still show "verified"?

Human Response:
```
[Write your verification notes here]
```

---

### 3.2 OptumGX Results Provenance

**Task:** The OptumGX capacity results (NcV=6.006, NcH=3.847, NcM=1.468) were computed during a single GUI session on 2026-04-10. They cannot be reproduced without OptumGX running.

Questions:
1. Are the OptumGX scripts (`run_optumgx_capacity_validation.py`) committed in the repo? [ ] Yes [ ] No
2. Can a reviewer without OptumGX verify the results independently? [ ] Yes [ ] No
3. Are the mesh parameters (element count, adaptivity iterations) documented? [ ] Yes [ ] No
4. Is the geometry (D, L, su, gamma) clearly stated in the script? [ ] Yes [ ] No

Human Response:
```
[Write your verification notes here]
```

---

## Part 4: Unit Consistency

### 4.1 SoilState Convention

**File:** `op3/standards/pisa.py` line 217

**Task:** The `SoilState` dataclass says `su_or_phi: float` with the docstring specifying `[Pa]` for clay and `[deg]` for sand.

Check these call sites and verify the units match:

| File | Line | Value passed | Expected unit | Correct? |
|------|------|-------------|--------------|---------|
| `tests/test_pisa.py` | 46 | `80.0e3` | Pa | [ ] |
| `tests/test_pisa.py` | 47 | `120.0e3` | Pa | [ ] |
| `tests/test_foundations.py` | 178 | `50.0` | Pa | [ ] |
| `tests/test_foundations.py` | 179 | `100.0` | Pa | [ ] |
| `scripts/pisa_demo_oc3.py` | varies | ___ | Pa | [ ] |

**AI flag:** `tests/test_foundations.py` passes 50.0 and 100.0 which would be 50 Pa (not 50 kPa). The test still passes because it only asserts `> 0`. Is this a bug?

Human Response:
```
[Write your verification notes here]
```

---

### 4.2 Magic Number Audit

**Task:** Find and document the physical meaning of each bare constant.

| File | Line | Number | Physical meaning | Source |
|------|------|--------|-----------------|--------|
| `OpenSeesPy_v4_dissipation.py` | 249 | `10000.0` | ___ | ___ |
| `run_all_cross_validations.py` | 227 | `0.059` | ___ | ___ |
| `run_all_cross_validations.py` | 748 | `39.18` | ___ | ___ |
| `run_remaining_gaps.py` | varies | `0.60` | ___ | ___ |
| `OpenSeesPy_v6` | 40 | `2.5` | ___ | ___ |
| `OpenSeesPy_v6` | 46 | `0.2433` | ___ | ___ |

**Tip:** For each number, ask "if I change this by 10%, what breaks?" If nothing breaks, it might be a tuning parameter. If the physics breaks, it should have a citation.

Human Response:
```
[Write your verification notes here]
```

---

## Part 5: Authorship Declaration

### 5.1 What the AI did vs what the human did

**Task:** For each category, write ONE sentence describing the human's role.

| Category | AI contribution | Human contribution |
|----------|----------------|-------------------|
| Framework architecture | Implemented all Python modules | ___ |
| Formula selection | Typed coefficients from papers | ___ |
| OptumGX analysis | Wrote scripts, extracted results | ___ |
| Cross-validation | Built 39-benchmark suite | ___ |
| Visualization | Created 34 figures | ___ |
| Dissertation writing | Drafted chapters | ___ |
| Field data interpretation | Processed RANSAC windows | ___ |

### 5.2 Committee Q&A Preparation

Write your answer to each question (1-2 sentences):

**Q1:** "How much of this code was written by AI?"
```
[Your answer]
```

**Q2:** "How do you know the formulas are correct?"
```
[Your answer]
```

**Q3:** "Can the cross-validation results be reproduced?"
```
[Your answer]
```

**Q4:** "What happens if the PISA coefficients are wrong?"
```
[Your answer]
```

**Q5:** "Did you verify the OptumGX results independently?"
```
[Your answer]
```

---

## Part 6: Checklist Summary

Mark each item when verified:

### Must-fix before defense
- [ ] 1.2: Verify/fix missing Gazetas cubic term in api_rp_2geo.py
- [ ] 1.1: Fix PISA sand/clay paper attribution swap in comments
- [ ] 2.1: Decide and document coupling sign convention
- [ ] 4.1: Fix test_foundations.py su_or_phi units (50 Pa vs 50 kPa)

### Must-disclose at defense
- [ ] 3.1: Acknowledge 20/29 benchmarks are hardcoded snapshots
- [ ] 3.2: Acknowledge OptumGX results require commercial software
- [ ] 5.1: Prepare clear AI/human contribution statement

### Should-fix before publication
- [ ] 4.2: Add citations for all magic numbers (0.059, 39.18, 0.60, 2.5)
- [ ] 1.3: Verify Efthymiou correction factors digit-by-digit
- [ ] 1.4: Confirm OWA lateral base factor is intentionally different from Gazetas

---

## Submission

When complete, save this file and share with your AI assistant:

```
"I have completed the Human Review Workbook. Here are my responses: [paste or attach]"
```

The AI will:
1. Cross-check your paper values against the code
2. Flag any remaining discrepancies
3. Generate fix commits for confirmed errors
4. Update the V&V report with your verification notes
