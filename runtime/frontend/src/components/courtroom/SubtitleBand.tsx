import clsx from "clsx";

import { roleTitle } from "@/lib/roles";
import type { Role } from "@/types";

/**
 * A fixed band under the courtroom carrying whatever is being said right now.
 *
 * Replaces the floating speech bubble, which was capped at `max-w-md` and sat
 * over the scene: a claim of two or three lines got cramped, and the bubble
 * covered the benches it was pointing at. The band has the full width, sits
 * below the figures, and keeps the speaker's name in one place so the eye does
 * not have to find it again each turn.
 *
 * Height is fixed rather than fitted to the text. A band that grew and shrank
 * with each turn would shift the whole courtroom up and down for the length of
 * the debate; reserving the space once costs a little emptiness on a short
 * line and buys a scene that holds still.
 *
 * It keeps showing the last thing said while the next model generates, rather
 * than blanking to "waiting". A turn takes 40 to 90 seconds, so blanking would
 * leave the band empty for most of the debate, and who is being waited on is
 * already in the status rail next to the elapsed clock.
 */

interface SubtitleBandProps {
  role: Role | null;
  /** The headline of the current turn: first claim, or first objection. */
  text: string | null;
}

const ROLE_ACCENT: Record<string, string> = {
  presenter: "border-l-bench-presenter",
  attacker_doctrinal: "border-l-bench-doctrinal",
  attacker_evidentiary: "border-l-bench-evidentiary",
  judge: "border-l-bench-judge",
};

export function SubtitleBand({ role, text }: SubtitleBandProps) {
  const speaking = Boolean(role && text);

  return (
    <div
      data-testid="subtitle-band"
      // A live region: the band is where a screen reader finds out what was
      // said, and turns arrive while the user may be reading the transcript.
      aria-live="polite"
      aria-atomic="true"
      className={clsx(
        "relative z-20 flex min-h-[4.75rem] flex-col justify-center gap-1 rounded-lg border border-court-rail/60 border-l-4 bg-court-ink/70 px-4 py-3 backdrop-blur transition-colors duration-300",
        (role && ROLE_ACCENT[role]) ?? "border-l-court-rail",
      )}
    >
      {speaking ? (
        <>
          <span className="font-display text-[11px] font-semibold uppercase tracking-widest text-court-gold/80">
            {roleTitle(role as Role)}
          </span>
          {/* The headline only — the full argument lives in the transcript.
              Two lines, then an ellipsis: a hard cap keeps the band's height
              honest, and anything longer belongs in the record anyway. */}
          <p className="line-clamp-2 font-record text-sm leading-relaxed text-court-fg/90">
            {text}
          </p>
        </>
      ) : (
        <p className="font-ui text-xs italic text-court-fg/40">
          The court is silent.
        </p>
      )}
    </div>
  );
}
