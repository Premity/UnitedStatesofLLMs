import { describe, expect, it } from "vitest";

import { bandFor } from "@/components/dissent/Confidence";

/**
 * The bands come from the judge's own instructions
 * (prompts/shared/judge_system.md), so that the label restates the standard
 * the model was held to rather than inventing a scale for the UI. If those
 * instructions change, these boundaries have to change with them.
 */
describe("confidence bands", () => {
  it.each([
    [1.0, "Settled"],
    [0.95, "Settled"],
    [0.9, "Settled"],
    [0.89, "Supported"],
    [0.81, "Supported"],
    [0.7, "Supported"],
    [0.69, "Contested"],
    [0.6, "Contested"],
    [0.5, "Contested"],
    [0.49, "Against"],
    [0.2, "Against"],
    [0.0, "Against"],
  ])("puts %s in %s", (confidence, label) => {
    expect(bandFor(confidence).label).toBe(label);
  });

  it("reads the boundaries as the prompt states them", () => {
    // "0.9+ requires settled law" — 0.9 is settled, not merely supported.
    expect(bandFor(0.9).label).toBe("Settled");
    // "0.5-0.7 is the right range for genuinely contested questions".
    expect(bandFor(0.5).label).toBe("Contested");
    expect(bandFor(0.7).label).not.toBe("Contested");
    // "Below 0.5 means you think the opposing position is more likely right".
    expect(bandFor(0.5).label).not.toBe("Against");
    expect(bandFor(0.499).label).toBe("Against");
  });

  it("gives every band a gloss, since the label alone is not self-explanatory", () => {
    for (const c of [0.95, 0.8, 0.6, 0.3]) {
      expect(bandFor(c).gloss.length).toBeGreaterThan(20);
    }
  });

  /**
   * `Verdict.confidence_band()` in council-core decides the same thing for the
   * Markdown export. Two implementations of one rule drift, and a record that
   * disagreed with the screen about how certain the court was would be worse
   * than either alone — so the boundaries are pinned here as the export sees
   * them, lowercase and all.
   */
  it("agrees with the Python band at every boundary", () => {
    const fromPython: [number, string][] = [
      [1.0, "settled"],
      [0.95, "settled"],
      [0.9, "settled"],
      [0.89, "supported"],
      [0.81, "supported"],
      [0.7, "supported"],
      [0.69, "contested"],
      [0.6, "contested"],
      [0.5, "contested"],
      [0.49, "against"],
      [0.2, "against"],
      [0.0, "against"],
    ];

    for (const [confidence, band] of fromPython) {
      expect(bandFor(confidence).label.toLowerCase()).toBe(band);
    }
  });
});
