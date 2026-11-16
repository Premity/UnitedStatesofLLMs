# Ruling — round {{ round_number }} of at most {{ max_rounds }}

## Question

{{ question }}

{% if facts %}
## Facts as given

{{ facts }}
{% endif %}

{% include "shared/_context.md" %}

---

## Arguments

{% for arg in arguments %}
**[{{ arg.id }}]** {{ arg.claim }}

{{ arg.reasoning }}

{% if arg.resolved_citations %}
Authority:
{% for rc in arg.resolved_citations %}
- {{ rc.citation.locator() }} — **{{ rc.status.value }}**{% if rc.note %} ({{ rc.note }}){% endif %}
{% endfor %}
{% endif %}

{% endfor %}

## Objections

{% for obj in objections %}
**[{{ obj.id }}]** raised by {{ obj.raised_by.value }} against {{ obj.target_argument_id }}

*{{ obj.ground }}*

{{ obj.reasoning }}

{% if obj.resolved_citations %}
Authority:
{% for rc in obj.resolved_citations %}
- {{ rc.citation.locator() }} — **{{ rc.status.value }}**
{% endfor %}
{% endif %}

{% endfor %}

---

## Your task

Rule on every objection listed above, then state your conclusion.

**Weighing the facts.** The facts as given are the record; they will not grow.
Intent, purpose and knowledge are rarely stated outright and are inferred from
conduct. Where an element has to be inferred, decide whether the facts taken as
a whole support that inference to the standard the question sets. An objection
that something "is not established" succeeds only if the facts do not support
the inference, not merely because they do not state it in terms.

**Answering the question.** Sustaining an objection removes or narrows the
argument it targets; it is not by itself an answer of No. Your conclusion
answers the question asked, on the law and the facts, using what survived.

Begin the conclusion with **"Yes."**, **"No."**, or **"Indeterminate."** to
answer the question directly. Use "Yes" when the proposition in the question is
affirmed and "No" when it is rejected; use "Indeterminate" only when the
question cannot be resolved on the arguments and facts provided.

Note the citation status markers. A citation marked `unresolved` or `misquoted`
did not check out against the corpus — the argument or objection resting on it
is unsupported, and you should say so.

Return JSON:

```
{
  "conclusion": "Your holding, stated plainly.",
  "reasoning": "How the surviving arguments support it, and why the sustained objections did not defeat it.",
  "confidence": 0.65,
  "confidence_reasoning": "Why this number and not a higher or lower one.",
  "rulings": [
    {
      "objection_id": "obj_xxxxxxxx",
      "disposition": "overruled",
      "reasoning": "Why this objection fails. Published in the dissent log."
    }
  ],
  "surviving_argument_ids": ["arg_xxxxxxxx"],
  "novel_objections_raised": true
}
```

`disposition` must be one of: `sustained`, `overruled`, `partial`, `unaddressed`.

Set `novel_objections_raised` to false if this round only repeated ground
already covered — that closes the proceeding.
