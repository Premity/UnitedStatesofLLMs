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
| raw | 4 | 4 | 2 | 0 | 0 | 0.500 (n=4) | 0.295 (n=4) | 0.307 (n=4) | 0.307 | N/A | N/A | N/A | not scored | api |
| rag | 4 | 4 | 2 | 0 | 0 | 0.500 (n=4) | 0.305 (n=4) | 0.420 (n=4) | 0.355 | 0.000 | 0.188 | N/A | not scored | api |
| single_attacker | 4 | 4 | 2 | 0 | 0 | 0.500 (n=4) | 0.287 (n=4) | 0.333 (n=4) | 0.272 | 0.035 | 0.000 | N/A | not scored | api |
| full_council | 4 | 4 | 1 | 0 | 0 | 0.750 (n=4) | 0.173 (n=4) | 0.370 (n=4) | -0.020 | 0.000 | 0.000 | 0.899 (n=4) | not scored | api |
| self_consistency | 4 | 4 | 2 | 0 | 0 | 0.500 (n=4) | 0.337 (n=4) | 0.390 (n=4) | 0.365 | 0.000 | 0.000 | N/A | not scored | api |

> **No intervals:** `raw` (n=4), `rag` (n=4), `single_attacker` (n=4), `full_council` (n=4), `self_consistency` (n=4) have fewer than 10 completed cases. These rows support no claim of a difference between arms; read the per-case table.

### Objection severity

Each cell is sustained / overruled. Severity is the attacker's own rating, advisory only. *Not stated* means no rating was given or the run predates the field; it is never counted as minor. An overruled fatal objection is the most informative dissent-log entry.

| Arm | Fatal | Material | Minor | Not stated | Overruled fatal |
| --- | ---: | ---: | ---: | ---: | ---: |
| raw | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 |
| rag | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 |
| single_attacker | 3 / 0 | 5 / 5 | 0 / 0 | 0 / 0 | 0 |
| full_council | 13 / 4 | 11 / 6 | 0 / 0 | 0 / 0 | 4 |
| self_consistency | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 |

### Per case

| Case | Truth | Arm | Predicted | Correct | Confidence | Unresolved | Misquoted | Eligible citations | Attacker independence | Reasoning overlap |
| --- | --- | --- | --- | :---: | ---: | ---: | ---: | ---: | ---: | ---: |
| icc_bemba_command | rejected | raw | affirmed | ✗ | 0.85 | 0 | 0 | 0 | — | — |
| icc_bemba_command | rejected | rag | affirmed | ✗ | 0.70 | 0 | 2 | 6 | — | — |
| icc_bemba_command | rejected | single_attacker | affirmed | ✗ | 0.68 | 2 | 0 | 13 | — | — |
| icc_bemba_command | rejected | full_council | affirmed | ✗ | 0.70 | 0 | 0 | 19 | 0.843 | — |
| icc_bemba_command | rejected | self_consistency | affirmed | ✗ | 0.85 | 0 | 0 | 7 | — | — |
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
| icty_mrksic_vukovar | affirmed | raw | affirmed | ✓ | 0.85 | 0 | 0 | 0 | — | — |
| icty_mrksic_vukovar | affirmed | rag | affirmed | ✓ | 0.92 | 0 | 0 | 3 | — | — |
| icty_mrksic_vukovar | affirmed | single_attacker | affirmed | ✓ | 0.75 | 0 | 0 | 10 | — | — |
| icty_mrksic_vukovar | affirmed | full_council | affirmed | ✓ | 0.75 | 0 | 0 | 13 | 0.891 | — |
| icty_mrksic_vukovar | affirmed | self_consistency | affirmed | ✓ | 0.88 | 0 | 0 | 2 | — | — |

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
