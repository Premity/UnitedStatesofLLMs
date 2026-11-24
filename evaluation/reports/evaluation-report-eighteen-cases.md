# Evaluation report

Bootstrap: 10,000 resamples; fixed seed 0.
Intervals are percentile 95% confidence intervals, printed only for an arm with at least 10 completed cases. Below that the arm shows point values and n alone: a few cases give too few distinct resamples for an interval to estimate anything.
Fabrication rate = unresolved / (total citations - out_of_corpus); out_of_corpus is excluded (ADR 0004).
Misquote rate = misquoted / (total citations - out_of_corpus), reported apart: the quote check is a loose token-overlap heuristic, not an exact lookup.
Independence = 1 - token-level Jaccard overlap between attacker objection grounds; measured only on runs where both attackers objected.
Reasoning overlap = share of the tribunal's key_reasoning points a run relied on, scored by hand on a 0-2 scale per point (docs/evaluation.md, section 5); the soft metric. Averaged across scorers; an unscored run shows —.

Settings for every scored result (frozen, ADR 0009):

- presenter: `groq/openai/gpt-oss-120b`
- attacker_doctrinal: `groq/qwen/qwen3.8-27b`
- attacker_evidentiary: `groq/openai/gpt-oss-20b`
- judge: `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free`
- prompts: `8205576bb484`
- embedding: `BAAI/bge-large-en-v1.5`

Citation index: `8ffefb5a30ab (24 instruments, 3482 locators)`.

## Real results

| Arm | Cases | Completed | Wrong | Errors | Timed out | Accuracy | Brier score | ECE | Overconfidence | Citation fabrication rate | Citation misquote rate | Attacker independence | Reasoning overlap | Judge backend |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| raw | 18 | 18 | 6 | 0 | 0 | 0.667 (n=18) (0.444-0.889) | 0.208 (n=18) (0.104-0.322) | 0.142 (n=18) (0.062-0.363) | 0.107 (-0.085-0.322) | N/A | N/A | N/A | not scored | api |
| rag | 18 | 18 | 6 | 0 | 0 | 0.667 (n=18) (0.444-0.889) | 0.223 (n=18) (0.103-0.355) | 0.187 (n=18) (0.108-0.427) | 0.150 (-0.048-0.367) | 0.000 (0.000-0.000) | 0.032 (0.000-0.086) | N/A | not scored | api |
| single_attacker | 18 | 18 | 5 | 0 | 0 | 0.722 (n=18) (0.500-0.889) | 0.194 (n=18) (0.086-0.315) | 0.144 (n=18) (0.068-0.363) | 0.087 (-0.098-0.297) | 0.008 (0.000-0.026) | 0.016 (0.000-0.038) | N/A | not scored | api |
| full_council | 18 | 18 | 6 | 0 | 0 | 0.667 (n=18) (0.444-0.889) | 0.191 (n=18) (0.093-0.296) | 0.187 (n=18) (0.111-0.386) | 0.111 (-0.078-0.314) | 0.036 (0.000-0.119) | 0.015 (0.000-0.031) | 0.896 (n=16) (0.870-0.922) | not scored | api |
| self_consistency | 18 | 15 | 7 | 3 | 0 | 0.533 (n=15) (0.267-0.800) | 0.254 (n=15) (0.113-0.411) | 0.325 (n=15) (0.158-0.525) | 0.288 (0.087-0.502) | 0.042 (0.000-0.148) | 0.014 (0.000-0.047) | N/A | not scored | api |


### Fictional and adjudicated cases

Fictional (`hyp_`) cases have invented facts, so no model can recall their outcome, and an authored ground truth, not a tribunal's. An arm that does well only on adjudicated cases may be recalling the judgment.

| Arm | Adjudicated accuracy | Adjudicated Brier | Fictional accuracy | Fictional Brier |
| --- | ---: | ---: | ---: | ---: |
| raw | 0.615 (n=13) (0.385-0.846) | 0.229 (n=13) (0.121-0.354) | 0.800 (n=5) | 0.152 (n=5) |
| rag | 0.615 (n=13) (0.385-0.846) | 0.253 (n=13) (0.117-0.402) | 0.800 (n=5) | 0.147 (n=5) |
| single_attacker | 0.692 (n=13) (0.462-0.923) | 0.219 (n=13) (0.092-0.363) | 0.800 (n=5) | 0.127 (n=5) |
| full_council | 0.615 (n=13) (0.308-0.846) | 0.219 (n=13) (0.111-0.338) | 0.800 (n=5) | 0.121 (n=5) |
| self_consistency | 0.400 (n=10) (0.100-0.700) | 0.302 (n=10) (0.139-0.474) | 0.800 (n=5) | 0.158 (n=5) |


### Objection severity

Each cell is sustained / overruled. Severity is the attacker's own rating, advisory only. *Not stated* means no rating was given or the run predates the field; it is never counted as minor. An overruled fatal objection is the most informative dissent-log entry.

| Arm | Fatal | Material | Minor | Not stated | Overruled fatal |
| --- | ---: | ---: | ---: | ---: | ---: |
| raw | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 |
| rag | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 |
| single_attacker | 21 / 1 | 25 / 6 | 1 / 1 | 0 / 0 | 1 |
| full_council | 65 / 14 | 61 / 12 | 3 / 0 | 0 / 0 | 14 |
| self_consistency | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 |

### Per case

| Case | Truth | Arm | Predicted | Correct | Confidence | Unresolved | Misquoted | Eligible citations | Attacker independence | Reasoning overlap |
| --- | --- | --- | --- | :---: | ---: | ---: | ---: | ---: | ---: | ---: |
| hyp_cluster_shared_control | indeterminate | raw | affirmed | ✗ | 0.85 | 0 | 0 | 0 | — | — |
| hyp_cluster_shared_control | indeterminate | rag | affirmed | ✗ | 0.85 | 0 | 0 | 5 | — | — |
| hyp_cluster_shared_control | indeterminate | single_attacker | affirmed | ✗ | 0.78 | 0 | 0 | 14 | — | — |
| hyp_cluster_shared_control | indeterminate | full_council | rejected | ✗ | 0.75 | 12 | 0 | 20 | 0.909 | — |
| hyp_cluster_shared_control | indeterminate | self_consistency | affirmed | ✗ | 0.88 | 3 | 0 | 4 | — | — |
| hyp_hospital_warning | rejected | raw | rejected | ✓ | 0.85 | 0 | 0 | 0 | — | — |
| hyp_hospital_warning | rejected | rag | rejected | ✓ | 0.95 | 0 | 0 | 8 | — | — |
| hyp_hospital_warning | rejected | single_attacker | rejected | ✓ | 0.88 | 0 | 0 | 14 | — | — |
| hyp_hospital_warning | rejected | full_council | rejected | ✓ | 0.95 | 0 | 1 | 7 | — | — |
| hyp_hospital_warning | rejected | self_consistency | rejected | ✓ | 0.95 | 0 | 0 | 7 | — | — |
| hyp_perfidy_ambulance | affirmed | raw | affirmed | ✓ | 0.95 | 0 | 0 | 0 | — | — |
| hyp_perfidy_ambulance | affirmed | rag | affirmed | ✓ | 0.98 | 0 | 0 | 3 | — | — |
| hyp_perfidy_ambulance | affirmed | single_attacker | affirmed | ✓ | 0.92 | 0 | 0 | 12 | — | — |
| hyp_perfidy_ambulance | affirmed | full_council | affirmed | ✓ | 0.85 | 0 | 0 | 15 | 0.929 | — |
| hyp_perfidy_ambulance | affirmed | self_consistency | affirmed | ✓ | 0.95 | 0 | 0 | 3 | — | — |
| hyp_pow_militia | rejected | raw | rejected | ✓ | 0.95 | 0 | 0 | 0 | — | — |
| hyp_pow_militia | rejected | rag | rejected | ✓ | 0.92 | 0 | 0 | 2 | — | — |
| hyp_pow_militia | rejected | single_attacker | rejected | ✓ | 0.95 | 0 | 0 | 6 | — | — |
| hyp_pow_militia | rejected | full_council | rejected | ✓ | 0.92 | 0 | 0 | 8 | — | — |
| hyp_pow_militia | rejected | self_consistency | rejected | ✓ | 0.92 | 0 | 0 | 3 | — | — |
| hyp_starvation_wells | affirmed | raw | affirmed | ✓ | 0.90 | 0 | 0 | 0 | — | — |
| hyp_starvation_wells | affirmed | rag | affirmed | ✓ | 0.95 | 0 | 0 | 4 | — | — |
| hyp_starvation_wells | affirmed | single_attacker | affirmed | ✓ | 0.95 | 0 | 0 | 12 | — | — |
| hyp_starvation_wells | affirmed | full_council | affirmed | ✓ | 0.90 | 0 | 0 | 11 | 0.964 | — |
| hyp_starvation_wells | affirmed | self_consistency | affirmed | ✓ | 0.95 | 0 | 0 | 4 | — | — |
| icc_bemba_command | rejected | raw | affirmed | ✗ | 0.85 | 0 | 0 | 0 | — | — |
| icc_bemba_command | rejected | rag | affirmed | ✗ | 0.70 | 0 | 2 | 6 | — | — |
| icc_bemba_command | rejected | single_attacker | affirmed | ✗ | 0.68 | 2 | 0 | 13 | — | — |
| icc_bemba_command | rejected | full_council | affirmed | ✗ | 0.70 | 0 | 0 | 19 | 0.843 | — |
| icc_bemba_command | rejected | self_consistency | affirmed | ✗ | 0.85 | 0 | 0 | 7 | — | — |
| icc_ntaganda_own_forces | affirmed | raw | affirmed | ✓ | 0.60 | 0 | 0 | 0 | — | — |
| icc_ntaganda_own_forces | affirmed | rag | affirmed | ✓ | 0.90 | 0 | 0 | 6 | — | — |
| icc_ntaganda_own_forces | affirmed | single_attacker | affirmed | ✓ | 0.85 | 0 | 0 | 13 | — | — |
| icc_ntaganda_own_forces | affirmed | full_council | affirmed | ✓ | 0.85 | 0 | 0 | 17 | 0.849 | — |
| icc_ntaganda_own_forces | affirmed | self_consistency | affirmed | ✓ | 0.85 | 0 | 0 | 3 | — | — |
| icj_croatia_serbia_genocide | rejected | raw | indeterminate | ✗ | 0.55 | 0 | 0 | 0 | — | — |
| icj_croatia_serbia_genocide | rejected | rag | indeterminate | ✗ | 0.55 | 0 | 0 | 4 | — | — |
| icj_croatia_serbia_genocide | rejected | single_attacker | rejected | ✓ | 0.68 | 0 | 1 | 14 | — | — |
| icj_croatia_serbia_genocide | rejected | full_council | rejected | ✓ | 0.75 | 0 | 0 | 32 | 0.849 | — |
| icj_croatia_serbia_genocide | rejected | self_consistency | indeterminate | ✗ | 0.55 | 0 | 0 | 8 | — | — |
| icj_nuclear_weapons_self_defence | indeterminate | raw | indeterminate | ✓ | 0.85 | 0 | 0 | 0 | — | — |
| icj_nuclear_weapons_self_defence | indeterminate | rag | indeterminate | ✓ | 0.55 | 0 | 0 | 5 | — | — |
| icj_nuclear_weapons_self_defence | indeterminate | single_attacker | indeterminate | ✓ | 0.70 | 0 | 0 | 10 | — | — |
| icj_nuclear_weapons_self_defence | indeterminate | full_council | indeterminate | ✓ | 0.75 | 0 | 0 | 11 | 0.886 | — |
| icj_nuclear_weapons_self_defence | indeterminate | self_consistency | error | — | — | — | — | — | — | — |
| icj_wall_gc_iv | affirmed | raw | affirmed | ✓ | 0.65 | 0 | 0 | 0 | — | — |
| icj_wall_gc_iv | affirmed | rag | affirmed | ✓ | 0.72 | 0 | 0 | 5 | — | — |
| icj_wall_gc_iv | affirmed | single_attacker | affirmed | ✓ | 0.92 | 0 | 0 | 11 | — | — |
| icj_wall_gc_iv | affirmed | full_council | indeterminate | ✗ | 0.65 | 0 | 0 | 10 | 0.885 | — |
| icj_wall_gc_iv | affirmed | self_consistency | indeterminate | ✗ | 0.40 | 0 | 0 | 4 | — | — |
| icty_boskoski_ljuboten | affirmed | raw | affirmed | ✓ | 0.70 | 0 | 0 | 0 | — | — |
| icty_boskoski_ljuboten | affirmed | rag | affirmed | ✓ | 0.88 | 0 | 0 | 9 | — | — |
| icty_boskoski_ljuboten | affirmed | single_attacker | affirmed | ✓ | 0.78 | 0 | 0 | 19 | — | — |
| icty_boskoski_ljuboten | affirmed | full_council | indeterminate | ✗ | 0.68 | 0 | 0 | 31 | 0.945 | — |
| icty_boskoski_ljuboten | affirmed | self_consistency | error | — | — | — | — | — | — | — |
| icty_galic_terror | affirmed | raw | affirmed | ✓ | 0.88 | 0 | 0 | 0 | — | — |
| icty_galic_terror | affirmed | rag | affirmed | ✓ | 0.95 | 0 | 0 | 5 | — | — |
| icty_galic_terror | affirmed | single_attacker | affirmed | ✓ | 0.88 | 0 | 0 | 16 | — | — |
| icty_galic_terror | affirmed | full_council | affirmed | ✓ | 0.75 | 0 | 0 | 24 | 1.000 | — |
| icty_galic_terror | affirmed | self_consistency | affirmed | ✓ | 0.95 | 0 | 0 | 5 | — | — |
| icty_gotovina_knin | rejected | raw | affirmed | ✗ | 0.65 | 0 | 0 | 0 | — | — |
| icty_gotovina_knin | rejected | rag | affirmed | ✗ | 0.85 | 0 | 1 | 2 | — | — |
| icty_gotovina_knin | rejected | single_attacker | affirmed | ✗ | 0.78 | 0 | 0 | 18 | — | — |
| icty_gotovina_knin | rejected | full_council | rejected | ✓ | 0.72 | 0 | 0 | 17 | 0.863 | — |
| icty_gotovina_knin | rejected | self_consistency | affirmed | ✗ | 0.78 | 0 | 0 | 3 | — | — |
| icty_halilovic_grabovica | rejected | raw | rejected | ✓ | 0.78 | 0 | 0 | 0 | — | — |
| icty_halilovic_grabovica | rejected | rag | rejected | ✓ | 0.78 | 0 | 0 | 8 | — | — |
| icty_halilovic_grabovica | rejected | single_attacker | rejected | ✓ | 0.78 | 0 | 3 | 27 | — | — |
| icty_halilovic_grabovica | rejected | full_council | rejected | ✓ | 0.85 | 0 | 2 | 28 | 0.932 | — |
| icty_halilovic_grabovica | rejected | self_consistency | error | — | — | — | — | — | — | — |
| icty_mrksic_vukovar | affirmed | raw | affirmed | ✓ | 0.85 | 0 | 0 | 0 | — | — |
| icty_mrksic_vukovar | affirmed | rag | affirmed | ✓ | 0.92 | 0 | 0 | 3 | — | — |
| icty_mrksic_vukovar | affirmed | single_attacker | affirmed | ✓ | 0.75 | 0 | 0 | 10 | — | — |
| icty_mrksic_vukovar | affirmed | full_council | affirmed | ✓ | 0.75 | 0 | 0 | 13 | 0.891 | — |
| icty_mrksic_vukovar | affirmed | self_consistency | affirmed | ✓ | 0.88 | 0 | 0 | 2 | — | — |
| icty_oric_srebrenica | rejected | raw | affirmed | ✗ | 0.70 | 0 | 0 | 0 | — | — |
| icty_oric_srebrenica | rejected | rag | affirmed | ✗ | 0.85 | 0 | 0 | 6 | — | — |
| icty_oric_srebrenica | rejected | single_attacker | affirmed | ✗ | 0.75 | 0 | 0 | 22 | — | — |
| icty_oric_srebrenica | rejected | full_council | rejected | ✓ | 0.75 | 0 | 2 | 31 | 0.959 | — |
| icty_oric_srebrenica | rejected | self_consistency | affirmed | ✗ | 0.78 | 0 | 0 | 8 | — | — |
| icty_prlic_old_bridge | rejected | raw | affirmed | ✗ | 0.68 | 0 | 0 | 0 | — | — |
| icty_prlic_old_bridge | rejected | rag | affirmed | ✗ | 0.75 | 0 | 0 | 4 | — | — |
| icty_prlic_old_bridge | rejected | single_attacker | affirmed | ✗ | 0.85 | 0 | 0 | 10 | — | — |
| icty_prlic_old_bridge | rejected | full_council | affirmed | ✗ | 0.78 | 0 | 0 | 15 | 0.818 | — |
| icty_prlic_old_bridge | rejected | self_consistency | affirmed | ✗ | 0.75 | 0 | 1 | 5 | — | — |
| scsl_norman_child_recruitment | affirmed | raw | affirmed | ✓ | 0.68 | 0 | 0 | 0 | — | — |
| scsl_norman_child_recruitment | affirmed | rag | affirmed | ✓ | 0.65 | 0 | 0 | 9 | — | — |
| scsl_norman_child_recruitment | affirmed | single_attacker | affirmed | ✓ | 0.68 | 0 | 0 | 14 | — | — |
| scsl_norman_child_recruitment | affirmed | full_council | indeterminate | ✗ | 0.65 | 0 | 0 | 27 | 0.812 | — |
| scsl_norman_child_recruitment | affirmed | self_consistency | affirmed | ✓ | 0.88 | 0 | 0 | 5 | — | — |

### Prompt hashes

**raw**
- `attacker_doctrinal/challenge.md`: `c18ca824b618334ab62a0bdd0e023a11c84f960efcc8ce04fae50385ff74933c`
- `attacker_evidentiary/challenge.md`: `c410b10f2db4ae73c4dec383ad7b1a5bfcc329235db9f0eb9128b20b79610f31`
- `judge/rule.md`: `aa219aad8969a565ef33bf3ef9552686f4399060c095da40301fd9a64949b2b7`
- `presenter/opening.md`: `9bffac26aa877e363860ce5ac0d0caf129b3aa32e86f5f91aeda833bd8c2afaa`
- `presenter/rebuttal.md`: `789d210f98051a00834f60e20e08a8a177622d621b9a7b94b71a72deaa31b8cd`
- `shared/_citation_rules.md`: `1be5b67127584968ece473769111c87d58106ee5ddbbd18ea31b3e714acdc4df`
- `shared/_context.md`: `f0b6d7b1215cdc2c5a8eed627167604853a398046f170a8cd9e93f54c972fe45`
- `shared/attacker_doctrinal_system.md`: `6921bde09c2dc084a3535784995329ff41a74f510a73ff374860e46c543f65b2`
- `shared/attacker_evidentiary_system.md`: `8e94062f81f1dad18a35bd65df9d19fa395e904cd1a4eef749aefd83d05dc02f`
- `shared/judge_system.md`: `ba07c6da09308e40937efa968d708dcd39db5cae8d4ce4271a7ee5354effd9e0`
- `shared/presenter_system.md`: `844587ced1044fc1cbc5f4cada452c4277b7cef334388230e61dc4dfcf25ff61`

**rag**
- `attacker_doctrinal/challenge.md`: `c18ca824b618334ab62a0bdd0e023a11c84f960efcc8ce04fae50385ff74933c`
- `attacker_evidentiary/challenge.md`: `c410b10f2db4ae73c4dec383ad7b1a5bfcc329235db9f0eb9128b20b79610f31`
- `judge/rule.md`: `aa219aad8969a565ef33bf3ef9552686f4399060c095da40301fd9a64949b2b7`
- `presenter/opening.md`: `9bffac26aa877e363860ce5ac0d0caf129b3aa32e86f5f91aeda833bd8c2afaa`
- `presenter/rebuttal.md`: `789d210f98051a00834f60e20e08a8a177622d621b9a7b94b71a72deaa31b8cd`
- `shared/_citation_rules.md`: `1be5b67127584968ece473769111c87d58106ee5ddbbd18ea31b3e714acdc4df`
- `shared/_context.md`: `f0b6d7b1215cdc2c5a8eed627167604853a398046f170a8cd9e93f54c972fe45`
- `shared/attacker_doctrinal_system.md`: `6921bde09c2dc084a3535784995329ff41a74f510a73ff374860e46c543f65b2`
- `shared/attacker_evidentiary_system.md`: `8e94062f81f1dad18a35bd65df9d19fa395e904cd1a4eef749aefd83d05dc02f`
- `shared/judge_system.md`: `ba07c6da09308e40937efa968d708dcd39db5cae8d4ce4271a7ee5354effd9e0`
- `shared/presenter_system.md`: `844587ced1044fc1cbc5f4cada452c4277b7cef334388230e61dc4dfcf25ff61`

**single_attacker**
- `attacker_doctrinal/challenge.md`: `c18ca824b618334ab62a0bdd0e023a11c84f960efcc8ce04fae50385ff74933c`
- `attacker_evidentiary/challenge.md`: `c410b10f2db4ae73c4dec383ad7b1a5bfcc329235db9f0eb9128b20b79610f31`
- `judge/rule.md`: `aa219aad8969a565ef33bf3ef9552686f4399060c095da40301fd9a64949b2b7`
- `presenter/opening.md`: `9bffac26aa877e363860ce5ac0d0caf129b3aa32e86f5f91aeda833bd8c2afaa`
- `presenter/rebuttal.md`: `789d210f98051a00834f60e20e08a8a177622d621b9a7b94b71a72deaa31b8cd`
- `shared/_citation_rules.md`: `1be5b67127584968ece473769111c87d58106ee5ddbbd18ea31b3e714acdc4df`
- `shared/_context.md`: `f0b6d7b1215cdc2c5a8eed627167604853a398046f170a8cd9e93f54c972fe45`
- `shared/attacker_doctrinal_system.md`: `6921bde09c2dc084a3535784995329ff41a74f510a73ff374860e46c543f65b2`
- `shared/attacker_evidentiary_system.md`: `8e94062f81f1dad18a35bd65df9d19fa395e904cd1a4eef749aefd83d05dc02f`
- `shared/judge_system.md`: `ba07c6da09308e40937efa968d708dcd39db5cae8d4ce4271a7ee5354effd9e0`
- `shared/presenter_system.md`: `844587ced1044fc1cbc5f4cada452c4277b7cef334388230e61dc4dfcf25ff61`

**full_council**
- `attacker_doctrinal/challenge.md`: `c18ca824b618334ab62a0bdd0e023a11c84f960efcc8ce04fae50385ff74933c`
- `attacker_evidentiary/challenge.md`: `c410b10f2db4ae73c4dec383ad7b1a5bfcc329235db9f0eb9128b20b79610f31`
- `judge/rule.md`: `aa219aad8969a565ef33bf3ef9552686f4399060c095da40301fd9a64949b2b7`
- `presenter/opening.md`: `9bffac26aa877e363860ce5ac0d0caf129b3aa32e86f5f91aeda833bd8c2afaa`
- `presenter/rebuttal.md`: `789d210f98051a00834f60e20e08a8a177622d621b9a7b94b71a72deaa31b8cd`
- `shared/_citation_rules.md`: `1be5b67127584968ece473769111c87d58106ee5ddbbd18ea31b3e714acdc4df`
- `shared/_context.md`: `f0b6d7b1215cdc2c5a8eed627167604853a398046f170a8cd9e93f54c972fe45`
- `shared/attacker_doctrinal_system.md`: `6921bde09c2dc084a3535784995329ff41a74f510a73ff374860e46c543f65b2`
- `shared/attacker_evidentiary_system.md`: `8e94062f81f1dad18a35bd65df9d19fa395e904cd1a4eef749aefd83d05dc02f`
- `shared/judge_system.md`: `ba07c6da09308e40937efa968d708dcd39db5cae8d4ce4271a7ee5354effd9e0`
- `shared/presenter_system.md`: `844587ced1044fc1cbc5f4cada452c4277b7cef334388230e61dc4dfcf25ff61`

**self_consistency**
- `attacker_doctrinal/challenge.md`: `c18ca824b618334ab62a0bdd0e023a11c84f960efcc8ce04fae50385ff74933c`
- `attacker_evidentiary/challenge.md`: `c410b10f2db4ae73c4dec383ad7b1a5bfcc329235db9f0eb9128b20b79610f31`
- `judge/rule.md`: `aa219aad8969a565ef33bf3ef9552686f4399060c095da40301fd9a64949b2b7`
- `presenter/opening.md`: `9bffac26aa877e363860ce5ac0d0caf129b3aa32e86f5f91aeda833bd8c2afaa`
- `presenter/rebuttal.md`: `789d210f98051a00834f60e20e08a8a177622d621b9a7b94b71a72deaa31b8cd`
- `shared/_citation_rules.md`: `1be5b67127584968ece473769111c87d58106ee5ddbbd18ea31b3e714acdc4df`
- `shared/_context.md`: `f0b6d7b1215cdc2c5a8eed627167604853a398046f170a8cd9e93f54c972fe45`
- `shared/attacker_doctrinal_system.md`: `6921bde09c2dc084a3535784995329ff41a74f510a73ff374860e46c543f65b2`
- `shared/attacker_evidentiary_system.md`: `8e94062f81f1dad18a35bd65df9d19fa395e904cd1a4eef749aefd83d05dc02f`
- `shared/judge_system.md`: `ba07c6da09308e40937efa968d708dcd39db5cae8d4ce4271a7ee5354effd9e0`
- `shared/presenter_system.md`: `844587ced1044fc1cbc5f4cada452c4277b7cef334388230e61dc4dfcf25ff61`
