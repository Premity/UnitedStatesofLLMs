# Evidentiary challenge — round {{ round_number }}

## Question before the tribunal

{{ question }}

{% if facts %}
## Facts as given

{{ facts }}
{% endif %}

{% include "shared/_context.md" %}

---

## Arguments to challenge

{% for arg in arguments %}
**[{{ arg.id }}]** {{ arg.claim }}

{{ arg.reasoning }}

{% if arg.citations %}
Authority relied on:
{% for c in arg.citations %}
- {{ c.locator() }}
{% endfor %}
{% endif %}

{% endfor %}

---

## Your task

Challenge the FACTUAL PREDICATE of these arguments. Stay within your mandate:
sufficiency of the evidence, whether mens rea can properly be inferred,
attribution, and what the record does not establish. Leave the legal test itself
to your counterpart.

Ask of each argument: what does this need the facts to establish, and do the
facts as given actually establish it?

Raise between zero and four objections. Quality over volume — each one is ruled
on individually, and weak objections are overruled.

Return JSON:

```
{
  "objections": [
    {
      "target_argument_id": "arg_xxxxxxxx",
      "ground": "One sentence stating the basis of the objection.",
      "reasoning": "Why the facts as given do not support what this claim requires.",
      "citations": []
    }
  ]
}
```

Return an empty `objections` list if the factual predicate holds.
