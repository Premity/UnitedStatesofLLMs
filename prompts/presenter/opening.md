# Opening argument

## Question

{{ question }}

{% if facts %}
## Facts as given

{{ facts }}
{% endif %}

{% include "shared/_context.md" %}

---

## Your task

Construct your position on the question above. Produce between two and five
discrete arguments — each a single contestable proposition, with its reasoning
and its supporting authority.

Return JSON:

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
