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

## Docs

- [ ] Relevant docs updated in this PR
- [ ] New decision with trade-offs? An ADR is included

## Notes for the reviewer

<!-- Anything worth flagging: known gaps, follow-ups, things you are unsure about. -->
