# 0010 — Corpus ids for annexed instruments, and how amendments are carried

**Status:** Proposed
**Date:** 2026-10-22

## Context

Corpus ids and citation locators are written into every stored run artifact, so
both are permanent (ADR 0007, ADR 0008, non-negotiable #5). Two instruments in
`corpus/manifests/treaties.json` cannot be indexed without first deciding what
they *are*.

### Hague IV carries an annex that renumbers from 1

The 1907 Convention has 9 articles. Annexed to it are the Hague Regulations,
which have 56 and begin again at Article 1. Verified against the ICRC source:

| unid | text |
| --- | --- |
| `article-1` | "The Contracting Powers shall issue instructions to their armed land forces…" |
| `regulations-art-1` | "The laws, rights, and duties of war apply not only to armies, but also to militia…" |
| `article-3` | "A belligerent party which violates the provisions of the said Regulations shall…" |
| `regulations-art-3` | "The armed forces of the belligerent parties may consist of combatants and non-combatants…" |

Different provisions, same numbers. The substantive law of means and methods is
in the **Regulations** — "Hague IV art. 23(g)" means Regulations art. 23, and
the Convention has no article 23 at all.

Under a single id, a model emitting the natural `hague_iv/art.23` would resolve
against whichever of the two the index happened to hold. That is worse than a
miss: the judge would check a quotation against text that is not the cited
provision, and the citation would be scored `resolved` or `misquoted` on the
wrong basis.

### The Rome Statute has been amended seven times, and the ICRC base text is already partly amended

The ICRC exposes the base statute and seven amendments as separate documents.
Inspecting them:

- The **base** node (129 entries) is **not the pristine 1998 text**. It contains
  the 2019 starvation clause, and its `8(2)(e)` list ends at `(xii)`.
- The **2010 war crimes amendment** restates the whole of article 8 (10,759
  chars against the base's 10,443; 98.4% similar) and adds `8(2)(e)(xiii)`
  through `(xv)`.
- The **2010 aggression amendment** adds three genuinely new articles with their
  own ids: `article-8bis`, `article-15bis`, `article-15ter`.
- Four further amendments are **bare fragments with no article number** —
  `unid: "amendment"`, a single sentence of inserted text (biological weapons,
  blinding lasers, fragments undetectable by x-ray) or an instruction
  ("Article 124 of the Rome Statute is deleted.").

So "include the amendments" is not one operation. Three different shapes need
three different treatments, and a naive merge would either lose `8(2)(e)(xiii)`
or index an unattached sentence under a locator nobody cites.

Indexing only the base is not a neutral default either. `rome_statute` would be
a listed instrument, so a correct citation to `rome_statute/art.8bis` resolves
`unresolved` — which ADR 0004 reserves for fabrication. A model citing real law
correctly would be scored as inventing it, and `fabrication_rate` would be
wrong in the direction that flatters our thesis.

## Decision

### 1. An annexed instrument that renumbers gets its own corpus id

| id | Document | Articles |
| --- | --- | --- |
| `hague_iv` | Hague Convention (IV), 1907 | 9 |
| `hague_iv_regs` | Hague Regulations, annexed to Hague IV | 56 |

The rule generalises: **if a document restarts article numbering, it is a
separate corpus id.** Collision becomes impossible by construction rather than
discouraged by convention.

This also makes a real error legible. `hague_iv/art.23` — the Convention stops
at 9 — resolves `unresolved`, correctly reporting that the model cited a
provision the named instrument does not have. Under a single id that same
mistake would silently return Regulations text and look correct.

### 2. The Rome Statute is indexed as a consolidated text, with provenance per span

One id, `rome_statute`, holding the statute **as amended**. Amendments are
merged by article, and every span records where its text came from:

```json
{
  "locator": "rome_statute/art.8(2)(e)(xiii)",
  "text": "Employing poison or poisoned weapons;",
  "source_document": "rome_statute_amd_war_crimes_2010",
  "in_force_from": 2010
}
```

Merge rules, one per observed shape:

| Shape | Treatment |
| --- | --- |
| Amendment restates a whole article (2010 war crimes, art. 8) | The amended text **replaces** the base article; the base version is not indexed |
| Amendment adds new articles (2010 aggression: `8bis`, `15bis`, `15ter`) | Indexed as ordinary spans under their own locators |
| Amendment is an unnumbered fragment (weapons amendments) | **Not indexed as a span.** Recorded in the manifest as a known gap |
| Amendment deletes an article (2015, art. 124) | The article is **not** indexed; the manifest records why |

`8bis` and `15bis` use the locator form ADR 0008 already permits —
`rome_statute/art.8bis`, with sub-paragraphs parenthesised as usual
(`rome_statute/art.8bis(2)(a)`). No format change.

### 3. The unnumbered weapons amendments are a declared gap

Three amendments insert a sentence into article 8 without the ICRC source
saying which sub-paragraph it becomes. Guessing the locator would be worse than
omitting the text: a wrong locator is indistinguishable from a fabrication when
a model cites the real one.

They are listed in the manifest with `status: "not_indexed"` and a reason, and
`docs/corpus.md` states the coverage limit. If a fixture ever turns on one, the
locator gets confirmed against the ICC's own consolidated text and added
deliberately.

## Consequences

**Gained:**

- No locator in the corpus addresses two different provisions.
- A citation to real post-2010 law resolves `resolved`, not `unresolved`, so
  `fabrication_rate` measures fabrication rather than our coverage gaps.
- Provenance per span: a result can state which version of article 8 the system
  was arguing from, which matters because the 2010 text is what is in force.

**Given up:**

- **Two ids for one treaty instrument.** Anyone reading the manifest has to
  learn that `hague_iv` and `hague_iv_regs` are one treaty. Documented in
  `docs/corpus.md`.
- **The consolidated Rome text is ours, not an official publication.** We built
  it by merging ICRC documents, and the merge is only as good as the rules
  above. The report must say the statute is a consolidated text assembled from
  the ICRC base plus the 2010 amendments, not a published consolidation.
- **Three weapons amendments are missing.** A citation to one resolves
  `unresolved` and would be scored as fabrication. This is a known, documented
  limitation rather than a silent one, but it is still wrong in that direction.
- **More fetching.** Eight documents for one instrument instead of one.

**What would make us revisit:** a fixture turning on a weapons amendment, or
the ICC publishing a consolidated text in a machine-readable form — which would
let us drop the merge entirely and cite an official consolidation.

**Constraint this creates:** `hague_iv_regs` and the Rome merge rules are fixed
once the first scored run writes artifacts. Changing either afterwards breaks
citation resolution for every stored run.
