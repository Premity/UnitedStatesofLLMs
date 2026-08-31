# Disclaimer

**This is a student research prototype. It is not legal advice and must not be
used as such.**

## What this system is

An academic experiment in whether structured adversarial debate between language
models produces better-calibrated, better-grounded analysis than a single model
pass. It was built for a university Generative AI module.

## What it is not

- It is **not** a legal research tool, and must not be relied on for legal research.
- It is **not** a substitute for a qualified lawyer in any jurisdiction.
- It must **not** be used in, or to prepare for, actual legal proceedings.
- It must **not** be used to assess the conduct of identifiable individuals,
  units, or states in any operational, advocacy, journalistic, or
  accountability context.
- Its output must **not** be represented as the view of any court, tribunal,
  institution, or qualified professional.

## Why we are explicit about this

The system produces output that *looks* authoritative. It cites treaty articles
and case paragraphs, it reasons in the register of a legal memorandum, and it
attaches a numeric confidence. That presentation is the point of the research —
and it is exactly what makes misuse plausible.

The known limitations are real and they are not incidental:

- **Models fabricate authority.** Citation validation catches locators that do
  not resolve against our corpus, but a citation that resolves can still be
  applied to a proposition it does not support. The check is on existence, not
  on relevance.
- **The corpus is small and curated.** It covers a deliberately narrow slice of
  IHL. Authority outside it is marked `out_of_corpus` and cannot be verified
  here — which is not the same as being wrong, and not the same as being right.
- **Confidence scores are model-generated.** They are calibrated against a small
  fixture set. They are an object of study, not a warranty.
- **Facts are taken as given.** The system reasons over the facts it is handed.
  It has no capacity to establish, verify, or weigh evidence.
- **Legal questions turn on context this system does not have** — procedural
  posture, jurisdictional limits, the full record, and the specific submissions
  the parties actually made.

## On the subject matter

This project deals with international humanitarian law: armed conflict, war
crimes, and the treatment of civilians. Those are not abstractions, and the
cases in the evaluation set concern real atrocities and real victims.

The system is a study of AI reasoning behaviour. It is not a mechanism for
adjudicating responsibility, and no output it produces should be presented as
bearing on the culpability of any real person or party.

## Attribution

Treaty text, jurisprudence, and UN documents are reproduced from their official
public sources for academic research. Each is linked to its source in the corpus
manifests. All rights remain with the originating institutions.
