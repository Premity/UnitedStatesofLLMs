# Prompt tuning log

Run each experiment on the same dev subset and record the prompt file's hash
from the result artifact or report. Keep held-out cases out of prompt tuning.

| Date (UTC) | Prompt file changed | Prompt hash | Cases used | Judge calls used | Accuracy | Brier | ECE | Notes |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 2026-11-12 | `prompts/judge/rule.md` | `69c27d4fbb` | 0 | 0 | - | - | - | Require explicit Yes/No/Indeterminate prefix; no evaluation metrics claimed. |
| 2026-11-12 | — (outcome parser in `evaluation/harness/run.py`) | — | 0 | 0 | - | - | - | Handle negation conservatively and return indeterminate when unclear; no evaluation metrics claimed. |
| 2026-11-12 | — (judge JSON mode in `packages/council-core/src/council_core/llm/client.py`) | — | 0 | 0 | - | - | - | Request JSON mode for structured judge calls; no evaluation metrics claimed. |

## How to run an experiment

1. Change exactly one file under `prompts/`.
2. Run the same arm on the same dev subset, using a fresh output directory so
   results from different prompt versions are not overwritten. For example:

   ```bash
   make eval-arm ARM=rag ARGS="--limit 5 --judge-backend local --output-dir data/eval/prompt-test-01"
   uv run python -m metrics.report --results-dir data/eval/prompt-test-01 --output evaluation/reports/prompt-test-01.md
   ```

3. Add a row above with the changed prompt file and its hash, cases run, judge
   calls used, accuracy, Brier score, ECE, and any relevant notes.
