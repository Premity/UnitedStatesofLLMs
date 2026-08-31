import clsx from "clsx";

import type { Role } from "@/types";

/**
 * What the active participant just said, in one line.
 *
 * Shows the headline only — the first claim or the first objection. The full
 * text lives in the transcript panel; the bubble is for reading at a glance
 * while the debate is running.
 */

interface SpeechBubbleProps {
  role: Role;
  text: string;
  /** Bubble points down-left for counsel on the left, down-right for the right. */
  side?: "left" | "right" | "center";
}

const ROLE_ACCENT: Record<string, string> = {
  presenter: "border-bench-presenter",
  attacker_doctrinal: "border-bench-doctrinal",
  attacker_evidentiary: "border-bench-evidentiary",
  judge: "border-bench-judge",
};

export function SpeechBubble({ role, text, side = "center" }: SpeechBubbleProps) {
  return (
    <div
      className={clsx(
        "animate-pop max-w-md rounded-lg border-2 bg-court-panel/95 px-4 py-3 shadow-xl backdrop-blur",
        ROLE_ACCENT[role] ?? "border-court-rail",
      )}
    >
      <p className="font-record text-sm leading-relaxed text-white/90">{text}</p>

      {/* Tail */}
      <div
        className={clsx(
          "absolute -bottom-2 h-4 w-4 rotate-45 border-b-2 border-r-2 bg-court-panel",
          ROLE_ACCENT[role] ?? "border-court-rail",
          side === "left" && "left-8",
          side === "right" && "right-8",
          side === "center" && "left-1/2 -translate-x-1/2",
        )}
      />
    </div>
  );
}
