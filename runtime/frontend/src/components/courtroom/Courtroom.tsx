import { useEffect, useState } from "react";

import { useCourtStore } from "@/store/courtStore";
import type { Role } from "@/types";

import { ObjectionFlourish } from "./ObjectionFlourish";
import { SpeechBubble } from "./SpeechBubble";
import { Sprite } from "./Sprite";

/**
 * The live view: four benches, a gallery, and whatever is happening right now.
 *
 * Layout mirrors an adversarial proceeding — the judge elevated at the back,
 * presenting counsel at the left bench, the two challengers at the right. The
 * sprite whose model is currently generating bobs and holds the speech bubble;
 * everyone else dims out.
 */

const PHASE_CAPTION: Record<string, string> = {
  idle: "The court is not in session.",
  retrieving: "Consulting the authorities…",
  presenting: "Counsel is presenting.",
  objecting: "Opposing counsel objects.",
  ruling: "The court is deliberating.",
  adjourned: "The court has ruled.",
  error: "Proceedings interrupted.",
};

const ROLE_WAITING: Record<string, string> = {
  retriever: "the clerk is consulting the corpus",
  presenter: "presenting counsel is preparing",
  attacker_doctrinal: "doctrinal counsel is reviewing",
  attacker_evidentiary: "evidentiary counsel is reviewing",
  judge: "the court is deliberating",
};

/**
 * How long the current wait has run.
 *
 * Elapsed, never estimated: a turn takes anywhere from 40 to 90 seconds and
 * nothing reports progress, so a countdown would be invented. Seeing the
 * seconds climb is what distinguishes a slow model from a hung one.
 */
function Elapsed({ since }: { since: number }) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    setNow(Date.now());
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [since]);

  const seconds = Math.max(0, Math.floor((now - since) / 1000));
  return <>{seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}m ${seconds % 60}s`}</>;
}

export function Courtroom() {
  const {
    phase, round, activeRole, utterance, flourish, verdict, turns, replayed,
    pendingRoles, pendingSince,
  } = useCourtStore();

  const isThinking = (role: string) => pendingRoles.includes(role as Role);

  // Both attackers run concurrently, so name the pair rather than one of them.
  const waitingOn =
    pendingRoles.length === 2 &&
    pendingRoles.every((r) => r.startsWith("attacker_"))
      ? "opposing counsel are reviewing"
      : pendingRoles.length > 0
        ? ROLE_WAITING[pendingRoles[0]]
        : null;

  // Model ids come off the most recent turn each role took.
  const modelFor = (role: string) =>
    [...turns].reverse().find((t) => t.role === role)?.model_id;

  return (
    <section className="relative overflow-hidden rounded-xl border border-court-rail bg-gradient-to-b from-court-bg to-court-ink p-6 shadow-2xl">
      {/* Wood panelling suggestion behind the benches */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.07]"
        style={{
          backgroundImage:
            "repeating-linear-gradient(90deg, rgb(var(--court-gold)) 0 2px, transparent 2px 28px)",
        }}
      />

      {flourish && <ObjectionFlourish objection={flourish} />}

      {/* Judge, elevated */}
      <div className="relative z-10 flex justify-center pb-2">
        <Sprite
          role="judge"
          label="The Bench"
          variant="judge"
          modelId={modelFor("judge")}
          speaking={activeRole === "judge"}
          thinking={isThinking("judge")}
        />
      </div>

      {/* Speech bubble sits between the bench and the counsel tables */}
      <div className="relative z-20 mx-auto flex min-h-[5.5rem] max-w-2xl items-center justify-center px-4">
        {utterance && activeRole && (
          <SpeechBubble role={activeRole} text={utterance} />
        )}
      </div>

      {/* Counsel benches */}
      <div className="relative z-10 grid grid-cols-2 gap-8 pt-2">
        <div className="flex justify-center">
          <Sprite
            role="presenter"
            label="Presenting Counsel"
            modelId={modelFor("presenter")}
            speaking={activeRole === "presenter"}
          thinking={isThinking("presenter")}
          />
        </div>

        <div className="flex justify-center gap-6">
          <Sprite
            role="attacker_doctrinal"
            label="Doctrinal"
            modelId={modelFor("attacker_doctrinal")}
            speaking={activeRole === "attacker_doctrinal"}
          thinking={isThinking("attacker_doctrinal")}
          />
          <Sprite
            role="attacker_evidentiary"
            label="Evidentiary"
            modelId={modelFor("attacker_evidentiary")}
            speaking={activeRole === "attacker_evidentiary"}
          thinking={isThinking("attacker_evidentiary")}
          />
        </div>
      </div>

      {/* Status rail */}
      <div className="relative z-10 mt-6 flex items-center justify-between border-t border-court-rail/60 pt-3">
        <span className="flex items-center gap-2 font-ui text-xs uppercase tracking-widest text-court-gold/80">
          {/* Who is actually working beats a generic phase caption: a debate
              spends most of its time waiting, and "presenting" while the
              attackers generate names the wrong bench. */}
          {waitingOn ?? PHASE_CAPTION[phase] ?? phase}
          {replayed && (
            <span
              data-testid="replay-marker"
              title="A recorded fixture. No models were called."
              className="rounded border border-court-gold/40 px-1.5 py-0.5 text-[10px] tracking-wider text-court-gold/70"
            >
              Recorded
            </span>
          )}
        </span>
        <span className="font-ui text-xs text-court-fg/40">
          {pendingSince !== null && (
            <span data-testid="elapsed" className="mr-2 tabular-nums">
              <Elapsed since={pendingSince} />
            </span>
          )}
          {round > 0 && `Round ${round}`}
          {verdict && ` · Confidence ${Math.round(verdict.confidence * 100)}%`}
        </span>
      </div>
    </section>
  );
}
