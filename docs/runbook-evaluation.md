# Runbook: running the evaluation

Step by step, for anyone on the team: set up a machine, check it matches
everyone else's, run cases, send the results back, and combine them into the
report. Why the evaluation is designed this way is in
[evaluation.md](evaluation.md); this page is only what to do.

It covers the rehearsal (GitHub #25: all five arms on one case, unattended)
and the scored run (#26: all five arms on the three core cases).

---

## 0. What you need

- The repo, on `develop`, up to date: `git checkout develop && git pull`.
- Docker running, with `docker compose` (v2).
- `uv` on your PATH. Check with `uv --version`; if it's missing,
  `curl -LsSf https://astral.sh/uv/install.sh | sh`, then open a new terminal.
- The **index kit** (`ihl-index-kit-<hash>.zip`), sent to you privately.
- Two free API keys, which are yours and never shared:

  | Key | Get it at | Used by |
  | --- | --- | --- |
  | `GROQ_API_KEY` | https://console.groq.com/keys | presenter and both attackers |
  | `OPENROUTER_API_KEY` | https://openrouter.ai/keys | the judge |

Every command below runs from the repo root.

---

## 1. Set up the machine (once)

1. `make setup`. Creates `.env` from `.env.example` if you don't have one,
   installs dependencies and hooks. Safe to re-run.
2. In `.env`, set the two keys. **Leave every `COUNCIL_*_MODEL` line and
   `EMBEDDING_MODEL` exactly as `.env.example` has them.** Every machine must
   run the same models; section 3 checks it.
3. `make up`. The first build takes several minutes. Then wait until
   `curl -fsS localhost:6333/healthz && echo ok` prints `ok`.
4. Import the index. Unzip the kit, then:

   ```bash
   mkdir -p data/bundles
   cp /path/to/unzipped/ihl-index-<hash>.tar data/bundles/
   make import-index FILE=data/bundles/ihl-index-<hash>.tar
   docker compose restart api
   ```

   Never run `make fetch`, `make index` or `make corpus` for the evaluation.
   An index you build yourself won't match everyone else's, and the embedding
   stage needs more memory than most laptops have.
5. Smoke test, offline, no quota:

   ```bash
   uv run python -m harness.run --all-arms --dry-run --case icty_galic_terror \
     --output-dir data/scratch/dry-run
   ```

   All five arms print a result line. Dry-run results are synthetic, so keep
   them out of `data/eval/`.

---

## 2. Know your limits before you spend them

Free tiers, per account. Each person's runs use their own keys, which is why
splitting cases across people is faster.

| Limit | Value | What it means |
| --- | --- | --- |
| OpenRouter judge, free tier | 50 requests/day | The harness caps itself at **40** and refuses to start a run that would pass it. |
| Judge calls per case, all five arms | 7 (A 1, B 1, C 2, D 2, E 1) | The harness reserves 3 attempts per call, **21 per case**, before it starts. |
| Groq, presenter (`gpt-oss-120b`) | 200,000 tokens per rolling 24 hours | Three full cases used one account's whole day on 2026-11-15. A case uses about 75,000. Failed and retried requests count too, so the result files undercount what Groq has charged. |
| Groq, presenter (`gpt-oss-120b`), per request | 8,000 tokens per minute on the free tier, and one request may not exceed it | The presenter's round 2 is the biggest request: 5,100–5,900 tokens by the model's own count before the rebuttal's trim, 3,100–3,800 after. Groq counts the same request higher (one was refused at 8,278) |
| Groq, doctrinal attacker (`qwen3.8-27b`) | on some accounts, 1,000 output tokens/minute | A request Groq expects to exceed it is refused outright. Its prompt keeps replies short (about 500–600 tokens) for this reason. |
| Time | about 15 minutes per case | Mostly the free judge: 27–341 s per call. |
| Quota tracking | per results folder, or per `--quota-log` | The harness counts today's judge calls from `quota_log.json` in the folder it writes to. Keep using `data/eval/`; if you move results, keep the log (section 5). `--quota-log PATH` points it at another log, one per OpenRouter account. |

**Plan on two cases per person per day, one case per command.** The
harness's judge count resets at 00:00 UTC (05:30 IST). Groq's daily token
limit doesn't: it's a rolling 24 hours, and its error says how long to wait.
Start a case on a fresh Groq day, not after a day of other runs.

**One machine, several accounts' keys.** `scripts/eval_rotate.py` runs the
pending `extended` cases one at a time and keeps one Groq key and one
OpenRouter key until a provider refuses for quota. Then it stops the harness,
rests only that key (for the wait Groq's error names), and resumes the case
with the next key: `--resume` restarts at the failed arm, so finished arms are
never re-run. An OpenRouter key also counts as spent when its own quota log in
`data/eval-quota/` has no room under the 40-attempt cap. Put one key per line in
`.keys/groq.txt` and `.keys/openrouter.txt` (gitignored). Use one key per
account: keys from the same account share its limit. The script names keys by
a hash prefix and never prints them.

```bash
uv run python scripts/eval_rotate.py --status   # keys, rests, pending cases and arms
uv run python scripts/eval_rotate.py            # run until done or every key rests
uv run python scripts/eval_rotate.py --wait     # ...and sleep until a key is back
uv run python scripts/eval_rotate.py --workers 2 --wait   # two cases at once
```

`--workers` is optional and defaults to 1. Each worker runs a different case
with its own Groq and OpenRouter key, so it needs at least that many keys of
each, and loads its own embedding model: about 1.5 GB of RAM a worker. On a
16 GB machine with an editor open, two is the ceiling.

---

## 3. Before every live run

Run all of these. Each catches something that is otherwise silent.

```bash
git checkout develop && git pull        # the frozen prompts and case facts
git status --short prompts evaluation   # must print nothing: no local edits
make up                                 # stack running
make index-status                       # no "Problems"; Fingerprint as in the kit
make eval-settings                      # "Matches the frozen settings"
```

`make eval-settings` prints your roster, prompt set, embedding model and index,
and compares them with `evaluation/frozen-settings.json` (section 4). A live run on a
machine that doesn't match refuses to start, naming each difference:

| It says | Fix |
| --- | --- |
| `<role> model is ... here` | Restore that `COUNCIL_*_MODEL` line in `.env` from `.env.example`, then `docker compose restart api` |
| `prompt set is ... here` | You have local edits under `prompts/`, or you're on the wrong branch: `git status`, `git checkout develop` |
| `EMBEDDING_MODEL is ... here` | Restore it from `.env.example`, `make down && make up`, then re-import the index |
| `citation index is ... here` | Re-import the kit's bundle (section 1, step 4) |

If it says **"Nothing is frozen yet"**, you're on a branch from before the
freeze; `git checkout develop && git pull`.

---

## 4. The frozen settings

The settings were frozen on 2026-11-16 (fingerprint `df941348ab17`), in the
same PR as the last prompt and case-fact changes, and before the rehearsal.
From then until the scored run ends, nothing under `prompts/`, the roster or
the case facts may change; a change invalidates every case already scored
(ADR 0009).

If a change is ever unavoidable, re-freeze deliberately: make the change, run
`make eval-freeze` on a machine that passes section 3, commit
`evaluation/frozen-settings.json` with it in one PR, re-run the rehearsal, and
re-run every case already scored.

---

## 5. The rehearsal (#25)

All five arms on one case, with nobody stepping in, on the frozen settings.

```bash
make eval ARGS="--case icty_galic_terror"
```

The harness prints the settings fingerprint and the judge budget, then asks
you to type `go`. The arms run in order A, B, C, D, E; E needs D's result,
because its sample count comes from D's call count.

It passes when:

- all five arms complete, with no errors and no `--resume`;
- E's `samples` is D's `total_calls` minus one (see the result files);
- the report's citation counts look plausible: few `unresolved`;
- both attackers' objections carry a `severity`;
- judge calls match the quota log.

Record the run in `tuning/LOG.md`. Then **move its results out of
`data/eval/`**, so they don't mix with the scored run, but **keep the quota
log**. The harness counts today's judge calls from the log in the results
folder, so a fresh folder would think nothing had been spent and could take
you past OpenRouter's real limit of 50.

```bash
mv data/eval data/eval-rehearsal-$(date +%Y%m%d)
mkdir -p data/eval && cp data/eval-rehearsal-$(date +%Y%m%d)/quota_log.json data/eval/
```

---

## 6. The scored run (#26)

### Who runs what

Split the three core cases by person, and write the split down where everyone
can see it before anyone starts. Each case is run **once**, by one person.

| Case | Run by | Date | Done |
| --- | --- | --- | --- |
| `icty_galic_terror` | machine 2 | 2026-11-16 | ✓ |
| `icty_gotovina_knin` | machine 1 | 2026-11-16 | ✓ |
| `icc_bemba_command` | machine 1 | 2026-11-16 | ✓ |
| `icty_mrksic_vukovar` (stretch) | machine 2 | 2026-11-16 | ✓ |

The scored run is done; its results are in `evaluation/results/scored-run/`
and its write-up in `evaluation/reports/write-up.md`. The extended tier has run
too: its results are in `evaluation/results/extended-run/`, and the
eighteen-case report is `evaluation/reports/evaluation-report-eighteen-cases.md`. Use this table again for
any later run.

The three stretch cases (`--tier stretch`) come only after all three core cases
are done, if quota allows (ADR 0012). The fourteen `extended` cases take the set
to twenty; run one with `--tier all --case <id>`, since a bare `--case` looks
only in the core tier.

### Running a case

One case per command:

```bash
make eval ARGS="--case icty_gotovina_knin"
```

Results go to `data/eval/<arm>/<case>.json`. Leave the machine alone while it
runs: about 15 minutes, longer on a slow judge day.

### When something fails

A failed or timed-out arm is saved as an error, not scored. Fix the cause, then
re-run with `--resume`: that skips the arms already done and re-runs only the
failed ones.

```bash
make eval ARGS="--case icty_gotovina_knin --resume"
```

| Error mentions | Cause | Do |
| --- | --- | --- |
| `Rate limit reached for model ...` (Groq), mentioning tokens per day | Your Groq account's token budget for the last 24 hours is spent | Stop; `--resume` after the wait the error names |
| `Request too large ... output tokens per minute (OTPM)` (Groq) | Your Groq tier's per-minute output limit for that model | Wait a few minutes and `--resume`; if it repeats, hand the case to someone else |
| `413 Request Entity Too Large` … `tokens per minute (TPM): Limit 8000` (Groq, `gpt-oss-120b`) | One presenter request is bigger than the free tier's whole per-minute allowance; waiting never fixes it | The rebuttal trims whole long articles to keep round 2 under it (`app/roles/presenter.py`). If it still appears, report it with the case: it means a debate's round 2 has outgrown the trim |
| `QuotaExceededError` | The run would pass the 40-call cap | Tomorrow |
| `Case timed out after 900 seconds` | A very slow judge | `--resume`; if it repeats, `--case-timeout 1500` |
| `differ from the frozen ones` | Section 3 | Fix the machine; never use `--allow-unfrozen-settings` for scored cases |
| `citation index ... is missing or empty` | Wrong folder, or the index was never imported | Run from the repo root; section 1, step 4 |
| `StructuredOutputError` | A model returned malformed JSON twice | `--resume` |
| `Qdrant is not reachable` | The stack is down | `make up` |

Stop after two consecutive judge failures; the harness does too.

### Sending your results back

When your cases are done, package them, check them, and send the zip
privately. It contains corpus text from the retrieved context.

```bash
zip -r eval-results-$(whoami)-$(date +%Y%m%d).zip data/eval
grep -rIlE "API_KEY|gsk_|sk-or-|Bearer " data/eval && echo "STOP: possible secret" || echo "clean"
make eval-settings > settings-$(whoami).txt   # send this too
```

Send nothing from `.env` or `data/logs/`.

---

## 7. Combining the results (one person)

1. Unzip everyone's results into one folder, keeping the
   `<arm>/<case>.json` layout. Each case was run by one person, so no file
   collides. Keep each person's `quota_log.json` aside, renamed. They aren't
   results, and every zip has one.

   ```bash
   for z in eval-results-*.zip; do unzip -o -q "$z" -d "unzipped-${z%.zip}"; done
   for arm in raw rag single_attacker full_council self_consistency; do
     mkdir -p "data/eval-combined/$arm"
     cp unzipped-*/data/eval/"$arm"/*.json "data/eval-combined/$arm/" 2>/dev/null || true
   done
   ```

   Check that `data/eval-combined/` holds five files per case run, one per arm
   (15 for the three core cases): `find data/eval-combined -name '*.json' | wc -l`.

   A zip made on Windows warns that it "appears to use backslashes as path
   separators"; `unzip` converts them, so the warning is harmless.

   Results written before 2026-11-16's harness fix carry arm E's old
   confidence (ADR 0011, amended). Rescore them; it changes only those, and
   only once:

   ```bash
   cd evaluation && python -m harness.artifacts rescore --results-dir ../data/eval-combined && cd ..
   ```
2. Generate the report:

   ```bash
   uv run python -m metrics.report --results-dir data/eval-combined \
     --output evaluation/reports/evaluation-report.md
   ```

   It refuses results scored against different citation indexes, or run under
   different rosters, prompts or embedding models. **Don't override that for
   the scored run.** It means a machine was off the frozen settings, and that
   case has to be re-run on a matching machine.
3. The report's header names the settings every result ran under. Commit the
   report, and the result files a reader needs to check the dissent logs
   (#26), without their corpus text: the repo is public (ADR 0014).

   ```bash
   cd evaluation && python -m harness.artifacts export \
     --results-dir ../data/eval-combined --output-dir results/scored-run && cd ..
   ```

   The exported files rebuild the same report: `--results-dir results/scored-run`.

Then score reasoning overlap by hand (#27, `docs/evaluation.md` section 5)
and write up, stating the limits #26 lists.
