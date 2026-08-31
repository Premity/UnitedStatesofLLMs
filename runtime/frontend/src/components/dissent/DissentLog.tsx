import { api } from "@/api/client";
import { useCourtStore } from "@/store/courtStore";
import type { Objection } from "@/types";

import { CitationChip } from "@/components/citations/CitationChip";

/**
 * The record.
 *
 * Deliberately sober where the courtroom is loud: this is the part someone
 * hands to a supervisor, so it reads as a document — parchment ground, serif
 * body, numbered entries. The dissent is the headline output of the whole
 * system, so it gets the most room.
 */
export function DissentLog() {
  const { verdict, runId, turns } = useCourtStore();

  if (!verdict) {
    return (
      <aside className="rounded-xl border border-record-rule bg-record-paper/95 p-8 text-center">
        <p className="font-record italic text-record-margin">
          The dissent log appears once the court has ruled.
        </p>
      </aside>
    );
  }

  const allArguments = turns.flatMap((t) => t.arguments);
  const surviving = allArguments.filter((a) =>
    verdict.surviving_argument_ids.includes(a.id),
  );

  return (
    <aside className="rounded-xl border border-record-rule bg-record-paper text-record-ink shadow-lg">
      <header className="border-b border-record-rule px-8 py-6">
        <h2 className="font-display text-2xl font-bold">Dissent Log</h2>
        {runId && (
          <p className="mt-1 font-ui text-xs text-record-margin">Run {runId}</p>
        )}

        {runId && (
          <div className="mt-4 flex gap-2">
            <a
              href={api.exportMarkdownUrl(runId)}
              className="rounded border border-record-margin/40 px-3 py-1.5 font-ui text-xs transition hover:bg-record-ink hover:text-record-paper"
            >
              Download Markdown
            </a>
            <a
              href={api.exportHtmlUrl(runId)}
              className="rounded border border-record-margin/40 px-3 py-1.5 font-ui text-xs transition hover:bg-record-ink hover:text-record-paper"
            >
              Download for print
            </a>
          </div>
        )}
      </header>

      <div className="space-y-8 px-8 py-6">
        <section>
          <h3 className="font-display text-lg font-semibold">Holding</h3>
          <p className="mt-2 font-record leading-relaxed">{verdict.conclusion}</p>

          <div className="mt-4 rounded border border-record-rule bg-white/50 p-4">
            <div className="flex items-baseline justify-between">
              <span className="font-ui text-xs uppercase tracking-wider text-record-margin">
                Calibrated confidence
              </span>
              <span className="font-display text-2xl font-bold">
                {Math.round(verdict.confidence * 100)}%
              </span>
            </div>
            {verdict.confidence_reasoning && (
              <p className="mt-2 font-record text-sm italic text-record-margin">
                {verdict.confidence_reasoning}
              </p>
            )}
          </div>

          <p className="mt-4 font-record leading-relaxed">{verdict.reasoning}</p>
        </section>

        {surviving.length > 0 && (
          <section>
            <h3 className="font-display text-lg font-semibold">
              Surviving arguments
            </h3>
            <ol className="mt-3 space-y-4">
              {surviving.map((arg) => (
                <li key={arg.id} className="border-l-2 border-record-rule pl-4">
                  <p className="font-record font-semibold">{arg.claim}</p>
                  <p className="mt-1 font-record text-sm leading-relaxed">
                    {arg.reasoning}
                  </p>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {arg.resolved_citations.map((rc, i) => (
                      <CitationChip key={i} resolved={rc} />
                    ))}
                  </div>
                </li>
              ))}
            </ol>
          </section>
        )}

        <section>
          <h3 className="font-display text-lg font-semibold">
            Dissent — objections overruled
          </h3>

          {verdict.dissent.length === 0 ? (
            <p className="mt-2 font-record italic text-record-margin">
              No objections were overruled.
            </p>
          ) : (
            <>
              <p className="mt-2 font-record text-sm text-record-margin">
                Challenges raised and rejected, recorded so the holding can be
                reviewed against the arguments it had to survive.
              </p>
              <ol className="mt-4 space-y-6">
                {verdict.dissent.map((obj) => (
                  <DissentEntry key={obj.id} objection={obj} />
                ))}
              </ol>
            </>
          )}
        </section>
      </div>
    </aside>
  );
}

const RAISER_LABEL: Record<string, string> = {
  attacker_doctrinal: "Doctrinal Counsel",
  attacker_evidentiary: "Evidentiary Counsel",
};

function DissentEntry({ objection }: { objection: Objection }) {
  return (
    <li className="border-l-2 border-court-crimson/50 pl-4">
      <p className="font-record font-semibold">{objection.ground}</p>
      <p className="mt-0.5 font-ui text-xs uppercase tracking-wider text-record-margin">
        {RAISER_LABEL[objection.raised_by] ?? objection.raised_by}
      </p>

      <p className="mt-2 font-record text-sm leading-relaxed">
        {objection.reasoning}
      </p>

      <div className="mt-2 flex flex-wrap gap-1.5">
        {objection.resolved_citations.map((rc, i) => (
          <CitationChip key={i} resolved={rc} />
        ))}
      </div>

      {objection.disposition_reasoning && (
        <div className="mt-3 rounded bg-record-ink/5 p-3">
          <span className="font-ui text-[11px] uppercase tracking-wider text-record-margin">
            Overruled because
          </span>
          <p className="mt-1 font-record text-sm leading-relaxed">
            {objection.disposition_reasoning}
          </p>
        </div>
      )}
    </li>
  );
}
