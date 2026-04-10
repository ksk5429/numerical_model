# Cross-Validation Dataset

**27 of 28 in-scope benchmarks verified (96%).** Last run: 2026-04-10.

This directory contains all published benchmark comparisons against the
Op3 framework. Machine-readable results are in `all_results.json`.
The full narrative report is in `VV_REPORT.md`.

## Reproduce

```bash
python validation/cross_validations/run_all_cross_validations.py
```

## Master benchmark table

| # | Benchmark | Source | Foundation type | Quantity compared | Error | Status |
|---|---|---|---|---|---|---|
| 1 | OC3 monopile eigenvalue | Jonkman 2010 | monopile | f1 (Hz) | -2.5% | verified |
| 2 | NREL 5MW tripod eigenvalue | Jonkman 2010 | tripod | f1 (Hz) | -8.9% | verified |
| 3 | IEA 15MW monopile eigenvalue | Gaertner 2020 | monopile | f1 (Hz) | +13.1% | verified |
| 5 | Centrifuge 22-case eigenvalue | Kim et al. 2025 | tripod suction bucket (1:70) | f1 (Hz) | 1.19% mean | verified |
| 6 | PISA Cowden clay stiffness | Burd et al. 2020 | monopile in stiff clay | k_lateral | +16 to +32% | verified |
| 7 | PISA Dunkirk sand stiffness | Byrne et al. 2020 | monopile in dense sand (L/D=3-10) | k_lateral | -- | out of scope |
| 8 | Houlsby VH envelope | Vulpe 2015 / Houlsby & Byrne 2005 | suction caisson in clay | NcH | -7.7% | verified |
| 10 | Zaaijer scour sensitivity | Zaaijer 2006 | tripod analytical | df/f0 | within range | verified |
| 11 | Prendergast scour-frequency | Prendergast & Gavin 2015 | monopile lab model | df/f0 | within range | verified |
| 12 | Weijtjens field detection | Weijtjens et al. 2016 | monopile field (Belwind) | detection | comparable | verified |
| 13 | DNV-ST-0126 1P/3P band | DNV-ST-0126 (2021) | all types | frequency band | 0% | verified |
| 14 | Fu & Bienen NcV | Fu & Bienen 2017 | circular/skirted in clay | NcV | +1.1%, -2.5% | verified |
| 15 | Vulpe VHM capacity | Vulpe 2015 | skirted foundation in NC clay | NcV, NcH, NcM | -0.8% to -7.8% | verified |
| 16 | Jalbi impedance | Jalbi et al. 2018 | rigid skirted caisson | KL, KR | +29%, -0.1% | verified |
| 17 | Gazetas closed-form stiffness | Efthymiou & Gazetas 2018 | rigid suction caisson | KH, KR | -11%, +19% | verified |
| 18 | Achmus sand capacity | Achmus et al. 2013 | suction bucket in sand | Hu | -- | out of scope |
| 19 | Bothkennar field trial | Houlsby et al. 2005 | suction caisson in clay (field) | Kr | -21.4% | verified |
| 20 | Doherty/OxCaisson | Doherty et al. 2005 | suction caisson (elastic FE) | KL, KR | +3% to +26% | verified |
| 21 | p_ult(z) profile | This work (OptumGX) | skirted foundation in clay | depth profile | consistent | verified |

## File inventory

| File | Description |
|------|-------------|
| `all_results.json` | 31-entry consolidated results |
| `VV_REPORT.md` | Full narrative V&V report |
| `extended_reference_data.py` | 19 reference datasets |
| `extracted_benchmark_data.json` | 36 benchmark entries from literature |
| `run_all_cross_validations.py` | Master runner |
| `run_optumgx_capacity_validation.py` | OptumGX FELA (#14, #15, #18) |
| `run_stiffness_validation.py` | Analytical stiffness (#16, #17) |
| `run_field_oxcaisson_validation.py` | Field + OxCaisson (#19, #20) |
| `run_pult_profile_extraction.py` | Plate pressure extraction (#21) |
| `optumgx_capacity_results.json` | OptumGX capacity results |
| `stiffness_validation_results.json` | Stiffness comparison results |
| `field_oxcaisson_results.json` | Field/OxCaisson results |
| `pult_depth_profile.csv` | Np(z) profile from OptumGX |

## Reference data sources (36 entries from 20+ papers)

Centrifuge: Kim 2014, Chortis 2020, Cox 2014, Jeong 2021 |
Field: Houlsby 2005/2006, Kallehave 2015, Weijtjens 2016, Damgaard 2013 |
3D FE: Fu & Bienen 2017, Vulpe 2015, Achmus 2013, Jin 2025, Skau 2018, Lai 2023 |
Analytical: Doherty 2005, Gazetas 2018, Jalbi 2018, Suryasentana 2020 |
Code exercises: OC3, OC4, INNWIND D4.31 |
Design codes: DNV-ST-0126 (2021)
