# Doctrinal challenge — round {{ round_number }}

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

Challenge the LEGAL CHARACTERISATION of these arguments. Stay within your
mandate: the correctness of the legal test, the elements of the crime, the
interpretation of the authority cited. Leave evidentiary sufficiency to your
counterpart.

Raise between zero and four objections. Quality over volume — each one is ruled
on individually, and weak objections are overruled.

Return JSON:

```
{
  "objections": [
    {
      "target_argument_id": "arg_xxxxxxxx",
      "ground": "One sentence stating the basis of the objection.",
      "reasoning": "The full argument for why this claim fails as a matter of law.",
      "citations": [
        {"type": "case", "instrument": "icty", "case_id": "icty_galic_tj",
         "paragraph": "58"}
      ]
    }
  ]
}
```

Return an empty `objections` list if the arguments are doctrinally sound.
