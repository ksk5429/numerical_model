# Cross-Validation Dataset

This directory contains all published benchmark comparisons against the
Op³ framework. Each subdirectory holds:

- `reference_data.py` — published values extracted from the literature
- `run_verification.py` — script that runs Op³ against the reference
- `results.json` — computed comparison with ratios and errors

## Master benchmark table

| # | Benchmark | Source | Foundation type | Quantity compared | Status |
|---|---|---|---|---|---|
| 1 | OC3 monopile eigenvalue | Jonkman 2010 NREL/TP-500-47535 | monopile | f₁ (Hz) | verified |
| 2 | NREL 5MW tripod eigenvalue | Jonkman 2010 | tripod | f₁ (Hz) | verified |
| 3 | IEA 15MW monopile eigenvalue | Gaertner 2020 NREL/TP-5000-75698 | monopile | f₁ (Hz) | verified |
| 4 | Gunsan 4.2MW tripod eigenvalue | This dissertation, Ch 6 | tripod suction bucket | f₁ (Hz) | verified |
| 5 | Centrifuge 22-case eigenvalue | This dissertation, Ch 3 | tripod suction bucket (1:70) | f₁ (Hz) | verified |
| 6 | PISA Cowden clay stiffness | Burd et al. 2020 Géotechnique | monopile in stiff clay | k_lateral (MN/m) | verified |
| 7 | PISA Dunkirk sand stiffness | Byrne et al. 2020 Géotechnique | monopile in dense sand | k_lateral (MN/m) | out of calibration |
| 8 | Houlsby & Byrne VH envelope | Villalobos et al. 2009 Géotechnique | suction caisson in clay | V-H capacity | pending |
| 9 | Zhu et al. mono-bucket lateral | Zhu et al. 2022 Ocean Engineering | mono-bucket in sand (centrifuge) | H_ult (kN) | pending |
| 10 | Zaaijer tripod frequency sensitivity | Zaaijer 2006 | tripod analytical | Δf/f₀ per S/D | pending |
| 11 | Prendergast scour-frequency | Prendergast & Gavin 2015 | monopile lab model | Δf/f₀ vs scour | pending |
| 12 | Weijtjens field frequency precision | Weijtjens et al. 2016 Wind Energy | monopile field (Belwind) | f₁ precision (Hz) | pending |
| 13 | DNV-ST-0126 1P/3P design check | DNV-ST-0126 (2021) | all types | frequency band compliance | verified |
