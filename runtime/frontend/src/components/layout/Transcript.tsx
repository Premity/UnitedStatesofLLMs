import { useCourtStore } from "@/store/courtStore";
import { CitationChip } from "@/components/citations/CitationChip";
import type { Turn } from "@/types";

/**
 * The running record, turn by turn.
 *
 * Sits under the courtroom while a debate is live — the bubble shows the
 * headline, this shows everything.
 */

const ROLE_LABEL: Record<string, string> = {
  presenter: "Presenting Counsel",
  attacker_doctrinal: "Doctrinal Counsel",
  attacker_evidentiary: "Evidentiary Counsel",
  judge: "The Bench",
  retriever: "Clerk",
};

const ROLE_ACCENT: Record<string, string> = {
  presenter: "border-bench-presenter",
  attacker_doctrinal: "border-bench-doctrinal",
  attacker_evidentiary: "border-bench-evidentiary",
  judge: "border-bench-judge",
};

export function Transcript() {
  const turns = useCourtStore((s) => s.turns);

  if (turns.length === 0) return null;

  return (
    <section className="space-y-3">
      <h2 className="font-ui text-xs uppercase tracking-widest text-court-gold/70">
        Transcript
      </h2>
      {turns.map((turn) => (
        <TurnCard key={turn.id} turn={turn} />
      ))}
    </section>
  );
}

function TurnCard({ turn }: { turn: Turn }) {
  return (
    <article
      className={`rounded-lg border-l-4 bg-court-panel/50 p-4 ${
        ROLE_ACCENT[turn.role] ?? "border-court-rail"
      }`}
    >
      <header className="flex items-baseline justify-between">
        <span className="font-display text-sm font-semibold text-white/85">
          {ROLE_LABEL[turn.role] ?? turn.role}
        </span>
        <span className="font-ui text-[11px] text-white/35">
          Round {turn.round_number} · {turn.model_id.split("/").pop()}
        </span>
      </header>

      {turn.arguments.map((arg) => (
        <div key={arg.id} className="mt-3">
          <p className="font-record text-sm font-semibold text-white/90">
            {arg.claim}
          </p>
          <p className="mt-1 font-record text-sm leading-relaxed text-white/65">
            {arg.reasoning}
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {arg.resolved_citations.map((rc, i) => (
              <CitationChip key={i} resolved={rc} />
            ))}
          </div>
        </div>
      ))}

      {turn.objections.map((obj) => (
        <div key={obj.id} className="mt-3">
          <p className="font-record text-sm font-semibold text-court-crimson">
            {obj.ground}
          </p>
          <p className="mt-1 font-record text-sm leading-relaxed text-white/65">
            {obj.reasoning}
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {obj.resolved_citations.map((rc, i) => (
              <CitationChip key={i} resolved={rc} />
            ))}
          </div>
        </div>
      ))}

      {turn.error && (
        <p className="mt-2 font-ui text-xs text-court-crimson">{turn.error}</p>
      )}
    </article>
  );
}
