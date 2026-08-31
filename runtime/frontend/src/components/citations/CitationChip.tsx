import clsx from "clsx";

import type { ResolvedCitation } from "@/types";

/**
 * One citation, with its resolution status visible.
 *
 * The status is the point. A citation that failed to resolve is shown as failed
 * rather than quietly dropped — a reader has to be able to see where the model
 * reached for authority that does not exist.
 */

const STATUS_STYLE: Record<string, string> = {
  resolved: "border-emerald-700/40 bg-emerald-50 text-emerald-900",
  unresolved: "border-red-700/50 bg-red-50 text-red-900 font-semibold",
  out_of_corpus: "border-amber-700/40 bg-amber-50 text-amber-900",
  misquoted: "border-red-700/50 bg-red-50 text-red-900 font-semibold",
};

const STATUS_LABEL: Record<string, string> = {
  resolved: "",
  unresolved: " · not found",
  out_of_corpus: " · unverified",
  misquoted: " · misquoted",
};

export function CitationChip({ resolved }: { resolved: ResolvedCitation }) {
  const { citation, status, corpus_text, source_url, note } = resolved;

  const locator = [
    citation.case_id ?? citation.instrument,
    citation.article && `art. ${citation.article}`,
    citation.paragraph && `¶${citation.paragraph}`,
    citation.rule_number && `rule ${citation.rule_number}`,
  ]
    .filter(Boolean)
    .join(" ");

  const body = (
    <span
      className={clsx(
        "inline-block rounded border px-2 py-0.5 font-ui text-[11px]",
        STATUS_STYLE[status] ?? "border-record-rule bg-white",
      )}
      title={note ?? corpus_text?.slice(0, 300) ?? undefined}
    >
      {locator}
      {STATUS_LABEL[status] ?? ""}
    </span>
  );

  return source_url ? (
    <a href={source_url} target="_blank" rel="noreferrer noopener">
      {body}
    </a>
  ) : (
    body
  );
}
