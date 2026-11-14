# Evaluation report

Bootstrap: 10,000 resamples; fixed seed 0.
Intervals are percentile 95% confidence intervals.
Fabrication rate = unresolved / (total citations - out_of_corpus); out_of_corpus is excluded.
Independence = 1 - token-level Jaccard overlap between attacker objection grounds.

## Real results

| Arm | Cases | Completed | Wrong | Errors | Timed out | Accuracy | Brier score | ECE | Overconfidence | Citation fabrication rate | Attacker independence | Judge backend |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| raw | 7 | 7 | 1 | 0 | 0 | 0.857 (n=7) (0.571-1.000) | 0.128 (n=7) (0.022-0.305) | 0.203 (n=7) (0.109-0.441) | -0.046 (-0.236-0.257) | N/A | N/A | api |

### Prompt hashes

**raw**
- `attacker_doctrinal/challenge.md`: `8d6983f5d6789edb9577937bee2745a3d4bc5434b5455ca6ea277a81344b5c02`
- `attacker_evidentiary/challenge.md`: `dfd46a5dfd71fc901d31a061641ddf1440727ad403609b53541dd844d1898f59`
- `judge/rule.md`: `bebc44b1be97fd8da19cec64d944e00b7669cfdcce7d5a8a4071ec107ea8e952`
- `presenter/opening.md`: `9bffac26aa877e363860ce5ac0d0caf129b3aa32e86f5f91aeda833bd8c2afaa`
- `presenter/rebuttal.md`: `789d210f98051a00834f60e20e08a8a177622d621b9a7b94b71a72deaa31b8cd`
- `shared/_citation_rules.md`: `7e70ff43107854e38881806af6c5db8668901c7387c9e543b18b41311220ccd0`
- `shared/_context.md`: `f0b6d7b1215cdc2c5a8eed627167604853a398046f170a8cd9e93f54c972fe45`
- `shared/attacker_doctrinal_system.md`: `6921bde09c2dc084a3535784995329ff41a74f510a73ff374860e46c543f65b2`
- `shared/attacker_evidentiary_system.md`: `8e94062f81f1dad18a35bd65df9d19fa395e904cd1a4eef749aefd83d05dc02f`
- `shared/judge_system.md`: `ba07c6da09308e40937efa968d708dcd39db5cae8d4ce4271a7ee5354effd9e0`
- `shared/presenter_system.md`: `844587ced1044fc1cbc5f4cada452c4277b7cef334388230e61dc4dfcf25ff61`
