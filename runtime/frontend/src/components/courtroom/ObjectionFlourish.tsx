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

/**
 * Whether an objection earns the full OBJECTION! slam.
 *
 * A flourish that fires on every attacker turn carries no information. There
 * is no severity field on an Objection (see ISSUES.md), so this uses the
 * strongest signal the data actually holds: an objection is loud when it is
 * *fully grounded* — it cites authority and every citation resolved against
 * the corpus. That is an attacker catching something with the text to back it.
 *
 * Deliberately not keyed to `unresolved` or `misquoted` citations. Those mark
 * the objection's own authority as bad, so slamming for them would celebrate
 * the attacker's mistake. Such objections are shown quietly; the red chip in
 * the transcript is what flags them.
 */
export function isLoud(objection: Objection): boolean {
  return (
    objection.resolved_citations.length > 0 &&
    objection.resolved_citations.every((rc) => rc.status === "resolved")
  );
}

/**
 * Which of a turn's objections to put on screen.
 *
 * The first one is not necessarily the one worth seeing. Prefer a grounded
 * objection, so a turn that lands one gets the slam rather than being
 * represented by whichever objection the model happened to emit first.
 */
export function headlineObjection(objections: Objection[]): Objection | null {
  return objections.find(isLoud) ?? objections[0] ?? null;
}

const RAISER_LABEL: Record<string, string> = {
  attacker_doctrinal: "Doctrinal Counsel",
  attacker_evidentiary: "Evidentiary Counsel",
};

/**
 * The spiked burst behind the word. Drawn rather than approximated with a
 * border-radius so the points stay sharp at any size, and sized by the box it
 * fills so the text never lands outside it.
 */
function Burst() {
  const points = Array.from({ length: 24 }, (_, i) => {
    const angle = (i / 24) * Math.PI * 2;
    const radius = i % 2 === 0 ? 50 : 41;
    return `${50 + radius * Math.cos(angle)},${50 + radius * Math.sin(angle)}`;
  }).join(" ");

  return (
    <svg
      aria-hidden
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
      className="absolute inset-0 h-full w-full"
    >
      <polygon
        points={points}
        fill="rgb(var(--court-crimson))"
        stroke="rgb(var(--record-paper))"
        strokeWidth="1.5"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}

/**
 * The quiet form, for an objection that is not fully grounded.
 *
 * Still visible, still says who objected, but it does not take the screen.
 * Sits at the foot of the courtroom rather than over it.
 */
function QuietObjection({ objection }: ObjectionFlourishProps) {
  return (
    <div className="pointer-events-none absolute inset-x-0 bottom-14 z-30 flex justify-center px-4">
      <div className="animate-pop max-w-lg rounded border border-court-crimson/60 bg-court-ink/95 px-4 py-2 shadow-lg">
        <div className="font-ui text-[10px] uppercase tracking-widest text-court-crimson">
          Objection · {RAISER_LABEL[objection.raised_by] ?? objection.raised_by}
        </div>
        <p className="mt-0.5 font-record text-sm leading-snug text-white/85">
          {objection.ground}
        </p>
      </div>
    </div>
  );
}

export function ObjectionFlourish({ objection }: ObjectionFlourishProps) {
  if (!isLoud(objection)) return <QuietObjection objection={objection} />;

  return (
    <div className="pointer-events-none absolute inset-0 z-30 grid place-items-center p-4">
      {/* One stack: the burst is the backdrop, everything else sits inside its
          padding. Previously the word and the attribution box were siblings,
          so the 8xl text overlapped the prose behind it. */}
      <div className="animate-slam relative w-full max-w-xl">
        <Burst />

        <div className="relative px-[12%] py-[9%] text-center">
          <div
            className="font-display text-4xl font-black uppercase leading-none tracking-tight text-white sm:text-5xl md:text-6xl"
            style={{ textShadow: "0 3px 0 rgba(0,0,0,0.35)" }}
          >
            Objection!
          </div>

          <div className="mt-3 font-ui text-[11px] uppercase tracking-widest text-court-gold">
            {RAISER_LABEL[objection.raised_by] ?? objection.raised_by}
          </div>

          <p className="mx-auto mt-1 max-w-md font-record text-sm leading-snug text-white">
            {objection.ground}
          </p>
        </div>
      </div>
    </div>
  );
}
