# Multi-seed summary

Seeds: results/seed-1, results/seed-2, results/seed-3

## casual_note

| Defense | BU % (mean ± sd) | UA % | ASR % | p vs none (per seed) | Benign flag rate % | USD / task |
|---|---|---|---|---|---|---|
| No defense | 64.9 | 55.4 | 35.3 | – | – | 0.00078 |
| Regex detector | 75.7 | 54.6 | 34.9 | 1 | 0.0 | 0.00087 |
| DeBERTa (block output) | 32.4 | 24.1 | 2.0 | 2.1e-25 | 89.5 | 0.00264 |
| LLM detector | 62.2 | 21.3 | 0.0 | 6.5e-27 | 2.1 | 0.00146 |
| LLM sanitizer | 54.1 | 48.6 | 0.0 | 6.5e-27 | 16.8 | 0.00093 |

## important_instructions

| Defense | BU % (mean ± sd) | UA % | ASR % | p vs none (per seed) | Benign flag rate % | USD / task |
|---|---|---|---|---|---|---|
| No defense | 71.2 ± 3.1 | 50.3 ± 3.5 | 54.8 ± 1.2 | – | – | 0.00067 ± 0.00002 |
| Spotlighting (delimiters) | 64.0 ± 4.1 | 49.9 ± 1.7 | 52.2 ± 1.2 | 0.31 / 0.14 / 1 | – | 0.00064 ± 0.00000 |
| Repeat user prompt | 64.0 ± 1.6 | 44.0 ± 0.6 | 21.8 ± 1.9 | 7.4e-26 / 9.7e-23 / 2.2e-16 | – | 0.00423 ± 0.00049 |
| Regex detector | 66.7 ± 1.6 | 24.2 ± 3.8 | 0.0 ± 0.0 | 5.7e-42 / 5.7e-42 / 1.8e-40 | 0.0 ± 0.0 | 0.00064 ± 0.00003 |
| DeBERTa (block output) | 36.0 ± 3.1 | 30.4 ± 2.5 | 10.6 ± 0.2 | 1.1e-32 / 3.2e-31 / 4.6e-29 | 86.1 ± 2.3 | 0.00242 ± 0.00024 |
| LLM detector | 62.2 ± 0.0 | 24.0 ± 5.2 | 0.0 ± 0.0 | 5.7e-42 / 5.7e-42 / 1.8e-40 | 3.6 ± 0.2 | 0.00079 ± 0.00008 |
| LLM sanitizer | 58.6 ± 1.6 | 49.5 ± 0.6 | 0.0 ± 0.0 | 5.7e-42 / 5.7e-42 / 1.8e-40 | 14.9 ± 1.8 | 0.00092 ± 0.00010 |

