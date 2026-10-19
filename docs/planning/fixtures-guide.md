# Writing case fixtures

Everyone writes ~15. This is the one task that cannot be hurried at the end, and
the one where a silent mistake corrupts every number in the final report.

Budget 20–40 minutes per case once you have a rhythm.

---

## What a fixture is

One adjudicated question where a real tribunal's holding supplies the ground
truth. The system sees the **question** and the **facts**; it never sees the
**holding**. That gap is what makes outcome agreement a measurement rather than
a lookup.

Schema: `EvaluationCase` in `evaluation/harness/cases.py`.
Worked example: `evaluation/cases/dev/icty_galic_terror.json`.

---

## The failure that matters

**Holding-leakage.** If the facts contain the tribunal's conclusion — or the
reasoning that forces it — every arm answers correctly, accuracy goes to ~100%,
and the ablation measures nothing.

It will not look like an error. The numbers will simply be too good, and nobody
can tell from the numbers alone whether that is a real result or a corrupted
fixture. **This is why every fixture gets a second reader.**

### What leakage looks like

> ❌ "The attacks were conducted with the **primary purpose of spreading
> terror** among the civilian population, which is prohibited under customary
> international law."

That is the holding, written into the facts. The system has nothing to decide.

> ✅ "Over approximately 23 months, forces under the accused's command conducted
> sniping and shelling against civilian areas of a besieged city. The attacks
> struck civilians queuing for water, attending funerals, crossing
> intersections. The pattern was sustained rather than isolated, and included
> attacks with no identifiable military objective in the vicinity."

Same case. The facts are all there — sustained pattern, civilian targets, no
military objective — but the legal characterisation is left to be made.

### The test

Read the facts alone. Ask: **could a competent lawyer reach the opposite
conclusion and still be arguing in good faith?**

- **Yes** → the fixture is sound.
- **No** → either the facts leak, or the case is too easy to be informative.

---

## Field by field

| Field | Shown to system | Guidance |
| --- | --- | --- |
| `id` | — | `<court>_<case>_<issue>`, lowercase. `icty_galic_terror` |
| `title` | — | Case name plus the issue. Enough to find it again |
| `court` | — | `ICTY` `ICTR` `ICC` `ICJ` |
| `year` | — | Year of the decision |
| `question` | **yes** | The legal question, answerable affirmed/rejected. No case names |
| `facts` | **yes** | Facts **as the tribunal found them**. No characterisation |
| `holding` | no | What the tribunal held, and on what basis |
| `outcome` | no | `affirmed` · `rejected` · `indeterminate` |
| `key_reasoning` | no | The grounds actually relied on, one per line |
| `difficulty` | — | See the rubric below |
| `source_case_id` | — | Corpus id if the judgment is indexed — **excluded from retrieval** |

### `question`

Phrase it as a legal question, not a case lookup.

> ✅ "Does a sustained campaign of sniping and shelling directed at civilians in
> a besieged city, conducted with the primary purpose of spreading terror,
> constitute a violation of the laws or customs of war?"

> ❌ "Was Galić guilty?" — unanswerable without the case; tests recall, not
> reasoning.

### `facts`

The facts the tribunal found, stripped of legal conclusion. Include what makes
the case contested — if the defence had a real argument, the facts supporting it
belong here too. A one-sided fact pattern makes an easy case.

### `key_reasoning`

The grounds the tribunal relied on, one per line. Used to score whether the
system anticipated the tribunal's *reasoning*, not just its result — a system
that gets the right answer for the wrong reason should score worse.

### `source_case_id`

If the judgment itself is in the corpus, set this. The harness excludes that
document from retrieval, so the system cannot read the answer back (T4-2).

**If you are unsure whether the judgment is indexed, set it anyway.** The cost
of excluding a document unnecessarily is small; the cost of the system
retrieving its own answer is a worthless result.

---

## Difficulty rubric

Agreed in TF-1. Two people labelling the same case independently should land on
the same label.

| Label | Criteria |
| --- | --- |
| `easy` | Settled law, clear facts. A competent lawyer would not seriously dispute the outcome |
| `medium` | Settled law applied to contested facts, **or** unsettled law on clear facts. Reasonable disagreement on one axis |
| `hard` | Contested on both law and facts, decided narrowly, or over significant dissent |

**Aim for a substantial share of `medium` and `hard`.** A set of `easy` cases
makes every arm look identical and the ablation shows nothing. The claim being
tested is about contested questions — which is exactly where a single-pass
model's overconfidence costs most.

---

## Workflow

1. **Pick a case** with a clear holding on a discrete IHL question. Coordinate
   so two people do not write the same one.
2. **Read the judgment** — at minimum the disposition and the reasoning on your
   issue.
3. **Write `holding`, `outcome` and `key_reasoning` first.** Getting the ground
   truth down before the facts makes leakage easier to notice.
4. **Write `facts`** from the tribunal's findings. Resist characterisation.
5. **Write `question`** last, once you know exactly what is being decided.
6. **Re-read the facts alone.** Apply the test above.
7. **Validate:** `uv run pytest evaluation/tests/test_fixtures.py`
8. **Get a second reader.** Someone else applies the test. This is not optional.

---

## Splitting the work

Coordinate by court or by subject so nobody duplicates:

| Area | Rough target |
| --- | --- |
| Distinction and proportionality in attack | ~15 |
| Protected persons and status | ~15 |
| Means and methods of warfare | ~15 |
| Command responsibility and attribution | ~15 |

Write into `evaluation/cases/dev/` first. The held-out set (TF-3) is partitioned
at the end — **and then not opened again.**

---

## What the validator catches

`make test` will fail on a malformed fixture: missing required field, unknown
`difficulty`, invalid `outcome`, duplicate `id`, malformed JSON.

**It cannot catch holding-leakage.** That is what the second reader is for. The
validator handles everything mechanical so review time goes to the one thing
that needs judgement.
