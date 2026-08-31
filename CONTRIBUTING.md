# Contributing

## Branching

```
main        ← protected. Release-ready; PRs from develop only.
develop     ← integration branch. Feature branches merge here.
feature/*   ← your work.
fix/*       ← bug fixes.
docs/*      ← documentation-only changes.
```

Branch off `develop`, never off `main`:

```bash
git checkout develop && git pull
git checkout -b feature/citation-validator
```

Name the branch after the change, not the ticket: `feature/parallel-attackers`
beats `feature/issue-14`.

## Commits

[Conventional Commits](https://www.conventionalcommits.org/), enforced by the
`commit-msg` hook and by CI. A commit that does not match is rejected before it
lands, which is deliberate — a scannable history is worth the friction.

```
<type>(<scope>): <subject in lower case, imperative mood>

[optional body explaining WHY, wrapped at 100]

[optional footer: Closes #12]
```

**Types:** `feat` `fix` `docs` `style` `refactor` `perf` `test` `build` `ci`
`chore` `revert`

**Scopes:** `api` `core` `frontend` `fetcher` `indexer` `eval` `prompts`
`corpus` `docker` `ci` `docs` `deps`

Good:

```
feat(api): stream turn-level events over SSE
fix(indexer): preserve subparagraph locators when chunking article 8
docs(adr): record why embeddings use fastembed rather than torch
test(core): cover fabricated-citation detection
```

Not good — and the hook will reject all of these:

```
Bug fixes
Frontend changes
WIP
feat: Added New Feature
```

The body is where you explain **why**. The diff already shows what changed; it
cannot show what you were thinking.

## Pull requests

1. Rebase onto `develop` before opening.
2. Run `make check` — lint, format, and tests. CI runs the same thing, and
   finding out locally is faster.
3. Fill in the PR template honestly. The checklist is there to catch the things
   that have actually broken this project before, not as a formality.
4. One reviewer approval before merge.
5. Merge into `develop` with `--no-ff` so the branch topology survives.

Keep PRs small enough to review properly. A 40-file PR gets rubber-stamped; a
6-file PR gets read.

### Merging locally

```bash
make merge-develop   # runs `make check`, then merges the current branch
make merge-main      # release: develop -> main
```

Both pass `--no-verify` on the merge commit, and only on the merge commit. Two
hooks necessarily fire on a merge — `no-commit-to-branch`, because merging into
`develop` means being on `develop`, and `conventional-pre-commit`, because git's
`Merge branch 'x' into y` is deliberately not a Conventional Commit. pre-commit
has no per-hook merge exemption. Nothing is skipped that was not already
checked: every commit being merged passed both hooks when it was made.

## Before you write code

```bash
make setup     # once, on a fresh clone
make up        # start the stack
make check     # lint + tests
```

## Where things go

| Adding… | Put it in |
| --- | --- |
| A domain type used by more than one service | `packages/council-core/src/council_core/models/` |
| A new debate node | `runtime/api/app/graph/nodes/` + wire it in `workflow.py` |
| A role's behaviour | `runtime/api/app/roles/` |
| A prompt change | `prompts/` — never inline in Python |
| A corpus source | `pipeline/fetcher/app/sources/` + the manifest |
| A metric | `evaluation/metrics/` |
| A UI component | `runtime/frontend/src/components/<area>/` |

**Prompts never go in Python string literals.** They live in `prompts/` so that
changing one is a reviewable diff and its hash lands in the run artifact.
A result attributed to a prompt that has silently changed is not a result.

## Testing expectations

`make test` must stay **fast and deterministic**. No network, no model calls.
Anything that talks to a real backend is marked `@pytest.mark.live` and excluded
from CI.

Two areas where tests are not optional:

- **The citation resolver.** If it silently accepts a fabricated citation, the
  project's central claim is false. Any change here needs a test showing the
  fabrication is still caught.
- **Debate termination.** An unbounded debate loop drains an API quota in
  minutes. Any change to round logic needs a test that it still terminates.

`make eval` is the separate, slow, quota-consuming path. It is never part of CI.

## Documentation

Update the docs in the same PR as the change. Specifically:

- Changed the architecture? → `docs/architecture.md`
- Made a decision with trade-offs? → a new `docs/adr/NNNN-*.md`
- Changed an endpoint or event shape? → `docs/api-contract.md`
- Changed a domain type? → `docs/data-model.md`
- Added a command? → the `Makefile` (with a `##` comment) and `docs/development.md`

## Secrets

Never commit a key. `gitleaks` runs in the pre-commit hook and in CI, but the
only reliable guard is not pasting one in the first place. If you do commit one:
rotate it immediately, then worry about the history.
