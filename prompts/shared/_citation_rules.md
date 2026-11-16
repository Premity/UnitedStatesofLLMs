## Citing authority

Every legal claim you make must carry a structured citation. Citations are
JSON objects, never prose references.

- Treaty:    `{"type":"treaty","instrument":"rome_statute","article":"8(2)(b)(iv)"}`
- Case:      `{"type":"case","instrument":"icty","case_id":"icty_galic_tj","paragraph":"58"}`
- Customary: `{"type":"customary","instrument":"customary_ihl","rule_number":14}`
- Resolution:`{"type":"resolution","instrument":"unga","article":"A/RES/3314"}`

Rules, without exception:

1. Cite ONLY authority that appears in the RETRIEVED CONTEXT below. Every
   citation is machine-checked against the corpus index; one that does not
   resolve is flagged as unsupported and weakens your position.
2. Copy the locator exactly as the retrieved context's heading gives it. The
   heading `[rome_statute/art.8(2)(b)(ii)]` is
   `{"type":"treaty","instrument":"rome_statute","article":"8(2)(b)(ii)"}`:
   every level of the article, `8(2)(b)(ii)` and never `8(b)(ii)`. A treaty
   article is always `"type":"treaty"`, never `"case"`.
3. Do NOT invent case names, paragraph numbers, or article subdivisions. A
   plausible-sounding citation that does not exist is the single worst failure
   available to you.
4. If the retrieved context does not support a point you want to make, say so
   explicitly and argue it as a matter of principle WITHOUT a citation. That is
   always better than fabricating one.
5. When you quote, put the exact words in `quoted_text`. The quotation is
   checked against the source span.
