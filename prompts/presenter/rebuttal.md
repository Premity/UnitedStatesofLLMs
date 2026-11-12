# Rebuttal — round {{ round_number }}

## Question

{{ question }}

{% if facts %}
## Facts as given

{{ facts }}
{% endif %}

{% include "shared/_context.md" %}

---

## Your arguments so far

{% for arg in prior_arguments %}
**[{{ arg.id }}]** {{ arg.claim }}

{{ arg.reasoning }}

{% endfor %}

## Objections raised against them

{% for obj in prior_objections %}
**[{{ obj.id }}]** ({{ obj.raised_by.value }}, against {{ obj.target_argument_id }})
{{ obj.ground }}

{{ obj.reasoning }}

{% endfor %}

---

## Your task

Respond to the objections. For each of your arguments, you may:

- **Defend it** — restate the claim with reasoning that meets the objection head on
- **Narrow it** — concede the part that fell and restate what survives
- **Abandon it** — omit it entirely from your response

Do not simply repeat your earlier reasoning louder. An objection that was right
should change your position, and a tribunal notices when it does not.

You may also raise a new argument if the objections opened a line you had not
taken.

Return JSON — the complete set of arguments you now stand on, in the same
shape as your opening:

```
{
  "arguments": [
    {
      "claim": "One sentence stating the proposition.",
      "reasoning": "Why it follows from the authority cited, applied to these facts.",
      "citations": [
        {"type": "treaty", "instrument": "rome_statute", "article": "8(2)(b)(iv)",
         "quoted_text": "the exact words you rely on"}
      ]
    }
  ]
}
```
