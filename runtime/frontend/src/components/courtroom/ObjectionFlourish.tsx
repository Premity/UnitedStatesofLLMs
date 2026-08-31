import type { Objection } from "@/types";

/**
 * The OBJECTION! slam.
 *
 * Fires when an attacker's turn lands with at least one objection. Deliberately
 * loud and deliberately brief — it draws the eye to the fact that a challenge
 * was raised, then clears so the substance can be read in the transcript.
 */

interface ObjectionFlourishProps {
  objection: Objection;
}

const RAISER_LABEL: Record<string, string> = {
  attacker_doctrinal: "Doctrinal Counsel",
  attacker_evidentiary: "Evidentiary Counsel",
};

export function ObjectionFlourish({ objection }: ObjectionFlourishProps) {
  return (
    <div className="pointer-events-none absolute inset-0 z-30 grid place-items-center">
      <div className="animate-slam text-center">
        <div
          className="font-display text-6xl font-black uppercase tracking-tight text-court-crimson md:text-8xl"
          style={{
            WebkitTextStroke: "3px #f7f3e9",
            textShadow: "0 6px 0 rgba(0,0,0,0.45)",
          }}
        >
          Objection!
        </div>
        <div className="mt-3 inline-block rounded bg-court-ink/90 px-4 py-2 shadow-lg">
          <div className="font-ui text-[11px] uppercase tracking-widest text-court-gold">
            {RAISER_LABEL[objection.raised_by] ?? objection.raised_by}
          </div>
          <div className="mt-1 max-w-lg font-record text-sm text-white/85">
            {objection.ground}
          </div>
        </div>
      </div>
    </div>
  );
}
