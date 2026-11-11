# Prompt tuning log

Run each experiment on the same dev subset and record the prompt file's hash
from the result artifact or report. Keep held-out cases out of prompt tuning.

| Date (UTC) | Prompt file changed | Prompt hash | Cases used | Judge calls used | Accuracy | Brier | ECE | Notes |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| YYYY-MM-DD | `prompts/...` | `<sha256>` | 0 | 0 | - | - | - | |

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
