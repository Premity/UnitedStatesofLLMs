import clsx from "clsx";

import type { Role } from "@/types";

/**
 * One participant at the bench.
 *
 * Placeholder art for now: a coloured plinth with the role's initial and a
 * nameplate. The bobbing animation and the speaking/idle states are what the
 * real sprites will slot into, so dropping in artwork later means replacing the
 * figure block and nothing else.
 */

interface SpriteProps {
  role: Role;
  label: string;
  modelId?: string;
  speaking: boolean;
  /**
   * This role's model is generating right now.
   *
   * The main state to design for: turns run 40 to 90 seconds and arrive
   * whole, with no token stream, so most of a debate is spent waiting. If
   * waiting does not read as activity the courtroom just looks broken.
   */
  thinking?: boolean;
  /** Judge sits elevated and centred; counsel sit at the benches. */
  variant?: "bench" | "judge";
}

const ROLE_COLOR: Record<string, string> = {
  presenter: "bg-bench-presenter",
  attacker_doctrinal: "bg-bench-doctrinal",
  attacker_evidentiary: "bg-bench-evidentiary",
  judge: "bg-bench-judge",
};

/**
 * The initial sits on the bench fill, so its colour follows that fill rather
 * than the page. The judge's bench is the accent in every theme, which is
 * light — hence the same token the primary button's label uses.
 */
const ROLE_INITIAL_COLOR: Record<string, string> = {
  judge: "text-court-on-gold/90",
};

const ROLE_INITIAL: Record<string, string> = {
  presenter: "P",
  attacker_doctrinal: "D",
  attacker_evidentiary: "E",
  judge: "J",
};

/**
 * Three dots that fill in turn.
 *
 * A deliberate choice not to show a progress bar: nothing reports how far
 * through a generation a model is, and a bar that advances on a guess would
 * claim knowledge the system does not have. Dots say "working" and nothing
 * more, which is the truth.
 */
function ThinkingDots() {
  return (
    <span
      aria-hidden
      className="absolute -bottom-1.5 flex gap-1 rounded-full bg-court-ink/90 px-2 py-1 ring-1 ring-court-gold/30"
    >
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="h-1 w-1 animate-pulse rounded-full bg-court-gold"
          style={{ animationDelay: `${i * 0.18}s`, animationDuration: "1.1s" }}
        />
      ))}
    </span>
  );
}

export function Sprite({
  role,
  label,
  modelId,
  speaking,
  thinking = false,
  variant = "bench",
}: SpriteProps) {
  // A thinking role is as present as a speaking one — it is the one everybody
  // is waiting on.
  const lit = speaking || thinking;

  return (
    <div
      className={clsx(
        "flex flex-col items-center gap-2 transition-all duration-300",
        lit ? "opacity-100" : "opacity-45 saturate-50",
      )}
    >
      {/* Figure — replace this block with real sprite art. */}
      <div
        className={clsx(
          "relative grid place-items-center rounded-t-full shadow-lg ring-2 ring-black/30",
          ROLE_COLOR[role] ?? "bg-court-rail",
          variant === "judge" ? "h-28 w-24" : "h-24 w-20",
          speaking && "animate-bob",
          // Breathing, slower than the speaking bob: considering, not talking.
          thinking && "animate-consider",
        )}
      >
        {thinking && <ThinkingDots />}

        <span
          className={clsx(
            "font-display text-3xl font-bold drop-shadow",
            ROLE_INITIAL_COLOR[role] ?? "text-record-paper/90",
          )}
        >
          {ROLE_INITIAL[role] ?? "?"}
        </span>

        {speaking && (
          <span className="absolute -right-1 -top-1 h-3 w-3 animate-pulse rounded-full bg-court-gold ring-2 ring-court-ink" />
        )}
      </div>

      {/* Nameplate */}
      <div className="min-w-[7rem] rounded border border-court-gold/30 bg-court-ink/80 px-2 py-1 text-center">
        <div className="font-display text-xs font-semibold tracking-wide text-court-gold">
          {label}
        </div>
        {modelId && (
          <div className="truncate font-ui text-[10px] text-court-fg/40">
            {modelId.split("/").pop()}
          </div>
        )}
      </div>
    </div>
  );
}
