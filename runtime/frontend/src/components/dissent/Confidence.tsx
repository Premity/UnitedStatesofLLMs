import type { Verdict } from "@/types";

/**
 * The judge's confidence, shown as what it is.
 *
 * A bare "81%" reads as a measured quantity. It is not: it is a number the
 * judge model chose, and this system has not yet demonstrated that those
 * numbers track how often it is right — the calibration metrics exist but no
 * evaluation has been run. Labelling it "Calibrated confidence" claimed a
 * property nobody has established.
 *
 * So the band leads and the number follows it. The bands are the ones the
 * judge is actually instructed to use (prompts/shared/judge_system.md), which
 * means the label restates the judge's own standard rather than inventing a
 * scale for the UI. The reasoning sits with it, because "why this number and
 * not a higher one" is the part a reader can actually check.
 */

export interface Band {
  label: string;
  /** What the judge was told this range means. */
  gloss: string;
  className: string;
}

/**
 * Thresholds from the judge's own instructions:
 *   0.9+      settled law, facts clearly meeting the test
 *   0.5-0.7   genuinely contested — where most IHL questions live
 *   below 0.5 the opposing position is more likely right
 *
 * The 0.7-0.9 gap in those instructions is treated as "supported": past
 * contested, short of settled.
 */
export function bandFor(confidence: number): Band {
  if (confidence >= 0.9) {
    return {
      label: "Settled",
      gloss: "Settled law, on facts that clearly meet the test.",
      className: "border-emerald-700/40 bg-emerald-50 text-emerald-900",
    };
  }
  if (confidence >= 0.7) {
    return {
      label: "Supported",
      gloss: "Past genuine contest, short of settled.",
      className: "border-sky-700/40 bg-sky-50 text-sky-900",
    };
  }
  if (confidence >= 0.5) {
    return {
      label: "Contested",
      gloss: "A genuinely contested question — where most IHL questions sit.",
      className: "border-amber-700/40 bg-amber-50 text-amber-900",
    };
  }
  return {
    label: "Against",
    gloss: "The opposing position is the more likely one.",
    className: "border-red-700/50 bg-red-50 text-red-900",
  };
}

export function Confidence({ verdict }: { verdict: Verdict }) {
  const band = bandFor(verdict.confidence);

  return (
    <div className="mt-4 rounded border border-record-rule bg-white/50 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-ui text-xs uppercase tracking-wider text-record-margin">
          The court&rsquo;s confidence
        </span>

        <span className="flex items-baseline gap-2">
          <span
            data-testid="confidence-band"
            title={band.gloss}
            className={`rounded border px-2 py-0.5 font-ui text-[11px] uppercase tracking-wider ${band.className}`}
          >
            {band.label}
          </span>
          {/* Secondary to the band: the judge's own figure, not a measurement. */}
          <span className="font-display text-lg font-bold text-record-ink/70">
            {verdict.confidence.toFixed(2)}
          </span>
        </span>
      </div>

      <p className="mt-2 font-record text-sm italic text-record-margin">{band.gloss}</p>

      {verdict.confidence_reasoning && (
        <p className="mt-2 font-record text-sm leading-relaxed">
          {verdict.confidence_reasoning}
        </p>
      )}

      <p className="mt-3 font-ui text-[11px] leading-relaxed text-record-margin">
        Self-reported by the judge model and not yet checked against decided
        cases. Read the reasoning above, not the number.
      </p>
    </div>
  );
}
