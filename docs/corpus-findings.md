# Building the corpus: what went wrong

Every problem below was found by running code against the real source and
looking at the output — not by reading documentation, which was wrong or
absent in most of these cases.

They share a shape worth naming up front. **Almost none of them raised an
exception.** A locator built at the wrong depth, a treaty whose articles
collide with its annex's, an embedding model that silently was not the one
configured — each produces a corpus that looks fine, indexes without
complaint, and quietly returns the wrong thing. In a system whose entire
output is a judgement about whether citations are real, that failure mode is
the one that matters.

Read this before changing the fetcher, the parsers, or the embedding model.

---

## 1. The source has no HTML

**Symptom.** Fetching `https://ihl-databases.icrc.org/en/ihl-treaties/api-1977`
returns 2,650 bytes containing no treaty text. So does every other URL on the
site, including article deep links.

**Cause.** The site is a React single-page app. The HTML is a shell; the text
arrives later from an API.

**Fix.** Read the JS bundle to find the backend, which is a public,
unauthenticated Drupal JSON:API:

```
/jsonapi/node/treaty                              111 treaties, 50 per page
/jsonapi/node/treaty/{uuid}/field_treaty_content  one treaty, by article
/jsonapi/node/rule                                the 161 customary rules
```

The whole corpus is about twenty requests. Articles arrive already separated,
with `field_treaty_content_unid` as `article-51`.

**What this cost us.** Two parallel investigations. One found the API by
reading the bundle; the other probed guessed paths, got HTTP 200 every time,
and concluded the site was unusable and we should scrape an unofficial Swedish
mirror instead. It was wrong, but reasonably so — see the next finding.

---

## 2. HTTP 200 means nothing on this host

**Symptom.** `/api/v1/treaties`, `/openapi.json`, `/swagger.json` and
`/sitemap.xml` all return **200**. All four return the same 2,650-byte SPA
shell.

**Why it matters.** A fetcher that checks `response.raise_for_status()` and
nothing else would accept every one of those as a successful fetch, parse zero
articles out of them, and report success. The corpus would be empty and no log
line would say so.

**Fix.** `IcrcClient._get` checks `content-type` and rejects anything that is
not JSON, with a message naming the likely cause. An empty node and a
zero-span parse are errors for the same reason. Covered by
`test_the_spa_shell_is_rejected_even_though_it_is_a_200`.

---

## 3. Hague IV contains two documents that both start at Article 1

**Symptom.** `hague_iv/art.3` is ambiguous. The Convention has an Article 3 and
so do the annexed Regulations, and they say different things:

| Locator source | Text |
| --- | --- |
| Convention art. 3 | "A belligerent party which violates the provisions of the said Regulations shall…" |
| Regulations art. 3 | "The armed forces of the belligerent parties may consist of combatants and non-combatants…" |

**Why it matters.** "Hague IV art. 23(g)" almost always means the
*Regulations* — that is where the law of means and methods lives, and the
Convention stops at Article 9. Under one corpus id, a model citing `art.23`
would resolve against whichever text the index happened to hold, and the judge
would check the quotation against the wrong provision. That is worse than a
miss: it is a confident answer about the wrong law.

**Fix.** Two corpus ids, `hague_iv` and `hague_iv_regs`
([ADR 0010](adr/0010-corpus-identity-and-amendments.md)). The general rule: *a
document that restarts article numbering is a separate corpus id.* The same
rule later applied to the five CCW protocols.

A side benefit: `hague_iv/art.23` now resolves `unresolved`, correctly
reporting that the model cited a provision the named instrument does not have.

---

## 4. The "original" Rome Statute is already amended

**Symptom.** Diffing the ICRC base node against the 2010 war crimes amendment:

```
base 10,443 chars | 2010 amendment 10,759 | similarity 0.984
base     8(2)(e) list ends at: (ix) (xi) (xii)
amended  8(2)(e) list ends at: (xiii) (xiv) (xv)
```

The base also contains the 2019 starvation clause.

**Why it matters.** Treating the base as "the 1998 text" would have been wrong
in both directions: it carries one later amendment and lacks another. And
indexing the base alone meant a correct citation to `rome_statute/art.8bis`
would resolve `unresolved` — the fabrication signal — because `rome_statute`
is a listed instrument. A model citing real law correctly would be scored as
inventing it, and `fabrication_rate` would be wrong in the direction that
flatters the thesis.

**Fix.** Index the statute as amended, with three merge rules because the
seven amendments come in three shapes: one restates a whole article, one adds
new articles (`8bis`, `15bis`, `15ter`), one deletes an article. Recorded per
amendment in the manifest.

**Not fixed.** Three weapons amendments arrive as a bare sentence with no
article number (`unid: "amendment"`). A guessed locator is indistinguishable
from a fabrication, so they are left out and listed in the manifest as a
declared gap. A citation to one resolves `unresolved`, which the metrics will
read as fabrication — say so in the report.

---

## 5. Sub-paragraph numbering cannot be read off the markup

**Symptom.** Two different shapes in one corpus. The Rome Statute gives one
`<p>` per item; AP I packs `(a)`, `(b)` and `(c)` into a single `<p>` separated
by line breaks, and closes with an unlabelled clause that belongs to the
paragraph above.

Worse, the unofficial mirror we considered numbers its paragraph elements
`A51S1`, `A51S2`… — and that index is a **sequential counter, not the legal
paragraph number**. `A51S5` is the `(a)/(b)/(c)` block under 51(4), so 51(5) is
`A51S7`. Mapping `S2 → (2)` happens to be right for 51(2) and wrong from 51(5)
onward.

**Why it matters.** `rome_statute/art.8(2)(b)(iv)` must be distinct from
`8(2)(b)(i)`. A locator built at the wrong depth addresses nothing, so the
provision is indexed and never retrieved, and a correct citation to it reads
as fabrication.

**Fix.** Recover the nesting from the labels themselves with a depth stack, not
from the markup. The hard part is that `(i)`, `(v)` and `(x)` are both roman
numerals and letters: `(a) (b) … (h) (i)` is a letter list reaching i, while
`(i) (ii) (iii)` is a roman list starting at i. Disambiguation is positional —
a label continues the list it plausibly succeeds.

---

## 6. Two numbering bugs the real data found

Neither raised. Both were found by running the parser over all nine documents
and grepping the output for suspicious locator shapes.

**Rome article 36(8) is written `8. (a) The States Parties shall…`** —
paragraph number and first sub-paragraph on one line. Dropping the inline
`(a)` left the roman list beneath it with no letter parent, minting
`36(8)(i)(ii)` for what is really `36(8)(a)(ii)`. Five bad locators corpus-wide.

**A list opening above 1 was accepted at any depth**, so `(i)` followed by
`(iv)` read as nesting and produced `(i)(iv)`. Now only allowed where no list
of that kind is already running.

**Method worth repeating:** after any parser change, re-run it across the whole
corpus and count the locators that look wrong. 651 articles yield no
sub-paragraphs, and all 651 are genuinely unnumbered prose — mostly Geneva
Convention articles, which are indexed whole. Zero articles that *start* with a
label fail to parse. That ratio is the regression test.

---

## 7. The configured embedding model does not exist

**Symptom.** `TextEmbedding(model_name="BAAI/bge-m3")` raises `ValueError`.

**Cause.** fastembed does not ship BGE-M3 — not in `TextEmbedding`, not in
`SparseTextEmbedding`, not in `LateInteractionTextEmbedding`. The name was in
`.env.example`, both compose files, the API settings and the indexer's
Dockerfile from the first commit, and [ADR 0001](adr/0001-no-torch-fastembed.md)
asserted it as fact.

**Why nothing caught it.** Nothing had embedded anything yet. The name was
config, and config is not executed.

**Fix.** `BAAI/bge-large-en-v1.5`, 1024 dimensions, verified to load and embed
before anything was changed. ADR 0001 amended: the decision (fastembed/ONNX, no
PyTorch) stands, the model name was wrong from the start.

**Related guard.** `ensure_collection` refuses to write into a collection whose
vector width differs from the embedder's, with a message naming a model change
as the likely cause. Non-negotiable #3 says a mismatch between indexer and API
returns meaningless scores silently; this makes one half of it loud.

---

## 8. UN resolutions are scanned images

**Symptom.** The UN Digital Library has a clean JSON API. The record for UNGA
3314 lists PDFs. Extracting text from the English PDF:

```
page 0: 0 chars
page 1: 0 chars
page 2: 0 chars
```

**Why it matters.** OCR errors in corpus text corrupt the `misquoted` signal
directly: a correct quotation fails to match the mangled stored text and is
reported as the model misquoting the law.

**Fix.** Take only the resolutions the ICRC serves as structured text — UNGA
2444 is there, and parses. The rest are out of scope, documented rather than
OCR'd badly.

---

## 9. Three packages were all called `app`

**Symptom.** `import app.index` raises `ModuleNotFoundError` from anywhere
outside a container, although the file plainly exists.

**Cause.** `runtime/api/app/`, `pipeline/fetcher/app/` and
`pipeline/indexer/app/` all declared the package name `app`. In the shared
workspace virtualenv, `app` resolves to whichever installed first — the API.

**Why it matters.** Pipeline code was unreachable from the test suite, which is
why neither stub had ever had a test.

**Fix.** Renamed to `fetcher` and `indexer`, and both test directories added to
`testpaths`. Beware a related trap: adding `__init__.py` to the new test
directories made them both claim the package name `tests`, breaking collection
the same way.

---

## 10. The base image carries a stale council-core

**Symptom.** A container fails with `ModuleNotFoundError` for a module that
works locally.

**Cause.** `council-core` is installed into `council-base` as its own layer.
Editing it leaves containers importing the old copy.

**Fix.** `make doctor` compares the content hashes of the local package against
the one inside the image. Timestamps do not work: a cached rebuild keeps the
original layer date, and `git checkout` rewrites mtimes without changing
anything.

**Measured rebuild cost**, which is why this matters:

| Change | Cost |
| --- | --- |
| Nothing | 3.5s |
| Service code only | 12s |
| Anything in `council-core` | **94s**, plus 12s per dependent image |

The local suite needs none of it. Develop and test locally; rebuild at stage
boundaries.

---

## The pattern

Seven of these ten produce **plausible wrong output rather than an error**. The
defences that actually caught things:

1. **Check content, not status.** HTTP 200, a non-empty file and a parse that
   returns something are all compatible with total failure.
2. **Run it over the whole corpus and count anomalies.** Both numbering bugs
   were found this way; neither would have been found by reading the code.
3. **Make the contract a test, not a convention.** The citation index is tested
   by driving the real `CitationResolver`, not a reimplementation of it.
4. **Refuse to guess a locator.** Where the source does not say which
   provision text belongs to, it is left out and recorded as a gap. A wrong
   locator is indistinguishable from a fabrication downstream.
