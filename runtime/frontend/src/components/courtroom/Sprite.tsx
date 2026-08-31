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
  /** Judge sits elevated and centred; counsel sit at the benches. */
  variant?: "bench" | "judge";
}

const ROLE_COLOR: Record<string, string> = {
  presenter: "bg-bench-presenter",
  attacker_doctrinal: "bg-bench-doctrinal",
  attacker_evidentiary: "bg-bench-evidentiary",
  judge: "bg-bench-judge",
};

const ROLE_INITIAL: Record<string, string> = {
  presenter: "P",
  attacker_doctrinal: "D",
  attacker_evidentiary: "E",
  judge: "J",
};

export function Sprite({
  role,
  label,
  modelId,
  speaking,
  variant = "bench",
}: SpriteProps) {
  return (
    <div
      className={clsx(
        "flex flex-col items-center gap-2 transition-all duration-300",
        speaking ? "opacity-100" : "opacity-45 saturate-50",
      )}
    >
      {/* Figure — replace this block with real sprite art. */}
      <div
        className={clsx(
          "relative grid place-items-center rounded-t-full shadow-lg ring-2 ring-black/30",
          ROLE_COLOR[role] ?? "bg-court-rail",
          variant === "judge" ? "h-28 w-24" : "h-24 w-20",
          speaking && "animate-bob",
        )}
      >
        <span className="font-display text-3xl font-bold text-white/90 drop-shadow">
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
          <div className="truncate font-ui text-[10px] text-white/40">
            {modelId.split("/").pop()}
          </div>
        )}
      </div>
    </div>
  );
}
