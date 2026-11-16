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

Raise between zero and three objections. Quality over volume — each one is ruled
on individually, and weak objections are overruled.

Keep each `reasoning` under 100 words: the decisive legal point and the
authority for it, not a survey of every point that could be made. A tight
objection is easier to sustain than a long one.

Return JSON:

```
{
  "objections": [
    {
      "target_argument_id": "arg_xxxxxxxx",
      "ground": "One sentence stating the basis of the objection.",
      "reasoning": "Why this claim fails as a matter of law, in under 100 words.",
      "severity": "fatal | material | minor",
      "citations": [
        {"type": "treaty", "instrument": "ap_i", "article": "51(2)"},
        {"type": "case", "instrument": "icty", "case_id": "icty_galic_tj",
         "paragraph": "58"}
      ]
    }
  ]
}
```

Rate each objection's `severity`, which is your assessment of how hard it
hits if sustained:

- `fatal` — the argument fails entirely.
- `material` — the argument survives but must be narrowed or qualified.
- `minor` — worth recording, but the argument stands substantially as put.

Rate honestly. The rating does not decide the ruling — the judge rules on your
reasoning — and marking everything `fatal` tells the court nothing.

Return an empty `objections` list if the arguments are doctrinally sound.
