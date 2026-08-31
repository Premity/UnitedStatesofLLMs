## Retrieved context

{% if context %}
The following spans were retrieved from the indexed corpus. These are the only
sources you may cite.

{% for span in context %}
### [{{ span.citation.locator() }}]
{% if span.source_url %}Source: {{ span.source_url }}{% endif %}

{{ span.corpus_text }}

{% endfor %}
{% else %}
*No corpus context was retrieved for this question. You must reason from
principle and say explicitly that you are doing so without authority.*
{% endif %}
