import { useCourtStore } from "@/store/courtStore";

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

export function Courtroom() {
  const { phase, round, activeRole, utterance, flourish, verdict, turns } =
    useCourtStore();

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
            "repeating-linear-gradient(90deg, #e8b84b 0 2px, transparent 2px 28px)",
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
          />
        </div>

        <div className="flex justify-center gap-6">
          <Sprite
            role="attacker_doctrinal"
            label="Doctrinal"
            modelId={modelFor("attacker_doctrinal")}
            speaking={activeRole === "attacker_doctrinal"}
          />
          <Sprite
            role="attacker_evidentiary"
            label="Evidentiary"
            modelId={modelFor("attacker_evidentiary")}
            speaking={activeRole === "attacker_evidentiary"}
          />
        </div>
      </div>

      {/* Status rail */}
      <div className="relative z-10 mt-6 flex items-center justify-between border-t border-court-rail/60 pt-3">
        <span className="font-ui text-xs uppercase tracking-widest text-court-gold/80">
          {PHASE_CAPTION[phase] ?? phase}
        </span>
        <span className="font-ui text-xs text-white/40">
          {round > 0 && `Round ${round}`}
          {verdict && ` · Confidence ${Math.round(verdict.confidence * 100)}%`}
        </span>
      </div>
    </section>
  );
}
