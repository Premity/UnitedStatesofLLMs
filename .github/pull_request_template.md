## Summary

<!-- What does this change and why? One or two sentences. -->

## Changes

-

## Type

- [ ] Feature
- [ ] Bug fix
- [ ] Refactor
- [ ] Docs / config
- [ ] Corpus / prompts

## Checks

- [ ] `make check` passes (lint, format, tests)
- [ ] Commits follow Conventional Commits
- [ ] Branch is rebased on `develop`
- [ ] No secrets, keys, or `.env` contents committed

## Debate pipeline (if touched)

- [ ] `DebateState` shape unchanged, or the change is intentional and documented
- [ ] Parallel nodes still return **only** the keys they write
      (returning full state raises `InvalidUpdateError`)
- [ ] Debate still terminates within `max_rounds` — covered by a test

## Citations (if touched)

- [ ] Fabricated citations are still detected — covered by a test
- [ ] `unresolved` and `out_of_corpus` remain distinguished
      (merging them makes the fabrication metric meaningless)
- [ ] Locator formats unchanged, or every stored run artifact is knowingly invalidated

## Prompts (if touched)

- [ ] Change is in `prompts/`, not inlined in Python
- [ ] Attacker mandates remain separated (doctrinal vs evidentiary)
- [ ] Ran at least one debate end-to-end and read the output

## Corpus (if touched)

- [ ] Manifest updated
- [ ] Citation locators are stable — no existing id was renamed
- [ ] Reindexed and confirmed retrieval still works

## Docs — not optional

Stale docs have cost this project real time: `CLAUDE.md` called the corpus
fetcher a stub for two weeks after it was built and running, and work was
proposed to build it again. Docs go stale in the PR that outdates them or
not at all, so tick these against the files, not from memory.

- [ ] **`ISSUES.md`** — anything this PR finished is marked `[RESOLVED]` or
      `[DONE]`, anything it found is filed, and the index table at the top
      matches the entries below it
- [ ] **`CLAUDE.md`** — still true about what is built, what is not, and the
      current state. Claiming something is a stub when it works sends the
      next person to rebuild it
- [ ] **A gotcha for anything that failed silently.** A wrong number or a
      lying status field belongs in `## Gotchas` with the command that
      reveals the truth
- [ ] **Test counts updated** where a doc quotes one
- [ ] `docs/api-contract.md` — if an SSE event, endpoint or payload changed
- [ ] `docs/architecture.md` / `docs/system-design.md` — if a component's
      state or a diagram's labels changed
- [ ] Nothing names a path that moved, or a count that is now wrong
- [ ] New decision with trade-offs? An ADR is included

If this PR genuinely touches no documented behaviour, say so in the notes
rather than leaving the section blank — "checked, nothing to update" is a
different claim from silence.

## Notes for the reviewer

<!-- Anything worth flagging: known gaps, follow-ups, things you are unsure about. -->
