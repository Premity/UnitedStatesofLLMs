import { useCourtStore } from "@/store/courtStore";
import { CitationChip } from "@/components/citations/CitationChip";
import type { Objection, Turn, Verdict } from "@/types";

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
  const { turns, verdict } = useCourtStore();

  if (turns.length === 0) return null;

  // Every objection raised so far, by id. The judge rules by mutating these
  // rather than by emitting anything of its own, so its card has to look them
  // up — see the comment on JudgeCard.
  const objections = new Map(
    turns.flatMap((t) => t.objections).map((o) => [o.id, o]),
  );

  return (
    <section aria-label="Transcript" className="space-y-3">
      <h2 className="font-ui text-xs uppercase tracking-widest text-court-gold/70">
        Transcript
      </h2>
      {turns.map((turn) =>
        turn.role === "judge" ? (
          <JudgeCard
            key={turn.id}
            turn={turn}
            objections={[...objections.values()]}
            verdict={verdict}
          />
        ) : (
          <TurnCard key={turn.id} turn={turn} />
        ),
      )}
    </section>
  );
}

/** Card shell — the chrome every turn shares. */
function Card({ turn, children }: { turn: Turn; children: React.ReactNode }) {
  return (
    <article
      className={`rounded-lg border-l-4 bg-court-panel/50 p-4 ${
        ROLE_ACCENT[turn.role] ?? "border-court-rail"
      }`}
    >
      <header className="flex items-baseline justify-between">
        <span className="font-display text-sm font-semibold text-court-fg/85">
          {ROLE_LABEL[turn.role] ?? turn.role}
        </span>
        <span className="font-ui text-[11px] text-court-fg/35">
          Round {turn.round_number} · {turn.model_id.split("/").pop()}
        </span>
      </header>
      {children}
    </article>
  );
}

const DISPOSITION_STYLE: Record<string, string> = {
  sustained: "border-emerald-600/50 bg-emerald-950/40 text-emerald-200",
  overruled: "border-court-crimson/50 bg-court-crimson/10 text-court-crimson",
  partial: "border-amber-600/50 bg-amber-950/30 text-amber-200",
  unaddressed: "border-court-rail bg-court-fg/5 text-court-fg/40",
};

const DISPOSITION_LABEL: Record<string, string> = {
  sustained: "Sustained",
  overruled: "Overruled",
  partial: "Partly sustained",
  unaddressed: "Not addressed",
};

/**
 * The bench's turn.
 *
 * The judge emits no arguments and no objections of its own: it rules by
 * setting `disposition` on the objections already raised, and its conclusion
 * goes into the Verdict. Rendered like any other turn, this card is therefore
 * always empty — which is what it was until now. It shows the rulings instead.
 */
function JudgeCard({
  turn,
  objections,
  verdict,
}: {
  turn: Turn;
  objections: Objection[];
  verdict: Verdict | null;
}) {
  const ruled = objections.filter((o) => o.disposition !== "unaddressed");

  return (
    <Card turn={turn}>
      {ruled.length > 0 && (
        <ol className="mt-3 space-y-3">
          {ruled.map((obj) => (
            <li key={obj.id}>
              <div className="flex flex-wrap items-baseline gap-2">
                <span
                  className={`rounded border px-1.5 py-0.5 font-ui text-[10px] uppercase tracking-wider ${
                    DISPOSITION_STYLE[obj.disposition] ?? ""
                  }`}
                >
                  {DISPOSITION_LABEL[obj.disposition] ?? obj.disposition}
                </span>
                <span className="font-ui text-[11px] text-court-fg/35">
                  {ROLE_LABEL[obj.raised_by] ?? obj.raised_by}
                </span>
              </div>
              <p className="mt-1 font-record text-sm text-court-fg/80">{obj.ground}</p>
              {obj.disposition_reasoning && (
                <p className="mt-1 font-record text-sm leading-relaxed text-court-fg/55">
                  {obj.disposition_reasoning}
                </p>
              )}
            </li>
          ))}
        </ol>
      )}

      {verdict && (
        <div className="mt-4 border-t border-court-rail/60 pt-3">
          <p className="font-record text-sm font-semibold text-court-gold">
            {verdict.conclusion}
          </p>
          <p className="mt-1 font-ui text-[11px] text-court-fg/35">
            Confidence {Math.round(verdict.confidence * 100)}% · full reasoning in
            the dissent log
          </p>
        </div>
      )}

      {ruled.length === 0 && !verdict && (
        <p className="mt-3 font-record text-sm italic text-court-fg/40">
          The court is deliberating.
        </p>
      )}

      {turn.error && (
        <p className="mt-2 font-ui text-xs text-court-crimson">{turn.error}</p>
      )}
    </Card>
  );
}

function TurnCard({ turn }: { turn: Turn }) {
  return (
    <Card turn={turn}>

      {turn.arguments.map((arg) => (
        <div key={arg.id} className="mt-3">
          <p className="font-record text-sm font-semibold text-court-fg/90">
            {arg.claim}
          </p>
          <p className="mt-1 font-record text-sm leading-relaxed text-court-fg/65">
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
          <p className="mt-1 font-record text-sm leading-relaxed text-court-fg/65">
            {obj.reasoning}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            {obj.resolved_citations.map((rc, i) => (
              <CitationChip key={i} resolved={rc} />
            ))}
            {/* The judge rules later, in place. Showing the outcome here means
                an objection can be read without scrolling to the bench. */}
            {obj.disposition !== "unaddressed" && (
              <span
                className={`rounded border px-1.5 py-0.5 font-ui text-[10px] uppercase tracking-wider ${
                  DISPOSITION_STYLE[obj.disposition] ?? ""
                }`}
              >
                {DISPOSITION_LABEL[obj.disposition] ?? obj.disposition}
              </span>
            )}
          </div>
        </div>
      ))}

      {turn.error && (
        <p className="mt-2 font-ui text-xs text-court-crimson">{turn.error}</p>
      )}
    </Card>
  );
}
