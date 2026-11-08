import clsx from "clsx";

import type { Objection } from "@/types";

/**
 * The OBJECTION! slam, over the sprite that raised it.
 *
 * Fires when an attacker's turn lands with at least one objection. Deliberately
 * loud and deliberately brief — it draws the eye to the fact that a challenge
 * was raised, then clears so the substance can be read in the transcript.
 *
 * Anchored to the objecting sprite rather than taking the whole courtroom.
 * Covering the scene hid the thing the objection was about, and said nothing
 * about *who* objected beyond a line of small text; a burst over one bench
 * says it by position. The objection's words moved to the subtitle band, which
 * is where everything else being said already appears — so the burst carries
 * only the word, at a size that fits a bench.
 *
 * It sits at the sprite's outer top corner — top-left for counsel on the left
 * of the room, top-right for counsel on the right. Outward from the centre, so
 * the burst never lands on the presenter between them, and mirrored so the two
 * attackers are told apart by position alone.
 */

/**
 * How long a flourish stays up before it clears, in milliseconds.
 *
 * Long enough to read the ground in the band underneath — the burst itself is
 * only a word, so the dwell is set by the prose, not the animation (which
 * finishes in 0.45s). Both the live stream and replay auto-play use this;
 * stepping mode ignores it and holds until the next click.
 */
export const FLOURISH_MS = 5000;

interface ObjectionFlourishProps {
  objection: Objection;
  /**
   * Which side of the courtroom this sprite sits on.
   *
   * Decides the corner the burst hangs from: the flourish cannot work it out
   * for itself, because a sprite does not know where it was placed.
   */
  side?: "left" | "right";
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
        fill="rgb(var(--court-crimson-deep))"
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
 * A small crimson tag on the sprite's own corner. Still says an objection was
 * raised, and position says by whom; the ground itself goes to the band like
 * any other utterance.
 */
function QuietObjection({ side }: { side: "left" | "right" }) {
  return (
    <div
      data-testid="objection-quiet"
      data-side={side}
      className={clsx(
        "animate-pop pointer-events-none absolute -top-2 z-30 whitespace-nowrap rounded border border-court-crimson/70 bg-court-ink/95 px-2 py-0.5 font-ui text-[10px] uppercase tracking-widest text-court-crimson shadow",
        // Same corner as the slam, so quiet and loud read as one thing at
        // different volumes rather than two different signals.
        side === "left" ? "-left-2" : "-right-2",
      )}
    >
      Objection
    </div>
  );
}

/**
 * Sized to the sprite it covers, not to the viewport.
 *
 * `-inset-x-6`/`-inset-y-4` lets the burst spill a little past the figure so
 * it reads as landing *on* the bench rather than being contained by it, while
 * staying far from the neighbouring sprite — the counsel columns are a third
 * of the courtroom wide, so there is room.
 */
export function ObjectionFlourish({
  objection,
  side = "left",
}: ObjectionFlourishProps) {
  if (!isLoud(objection)) return <QuietObjection side={side} />;

  return (
    <div
      data-testid="objection-slam"
      data-side={side}
      // Hung from the outer top corner and overhanging the figure, so the
      // sprite stays readable underneath. Sized in its own right rather than
      // by inset, because an inset burst is only ever as big as the bench.
      className={clsx(
        "animate-slam pointer-events-none absolute -top-10 z-30 grid h-24 w-40 place-items-center sm:h-28 sm:w-48",
        side === "left" ? "-left-10" : "-right-10",
      )}
    >
      <Burst />

      <div
        className="relative px-[10%] text-center font-display text-xl font-black uppercase leading-none tracking-tight text-record-paper sm:text-2xl"
        style={{ textShadow: "0 2px 0 rgba(0,0,0,0.35)" }}
      >
        Objection!
      </div>
    </div>
  );
}
