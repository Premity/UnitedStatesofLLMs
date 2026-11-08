import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Courtroom } from "@/components/courtroom/Courtroom";
import { SubtitleBand } from "@/components/courtroom/SubtitleBand";
import { roleSentence, roleShort, roleTitle } from "@/lib/roles";
import { useCourtStore } from "@/store/courtStore";
import type { Turn } from "@/types";

/**
 * Courtroom staging: the subtitle band and the bench layout.
 *
 * The band replaced a floating bubble and the counsel row became three
 * columns, so these assert the things that were wrong before — the speaker is
 * named, a long claim does not stretch the band, and the sprites sit in a
 * fixed order rather than wherever the turns arrived.
 */

function turn(role: Turn["role"], claim: string, round = 1): Turn {
  return {
    id: `turn_${role}_r${round}`,
    role,
    round_number: round,
    model_id: "groq/openai/gpt-oss-120b",
    arguments: [{ claim, reasoning: "because", citations: [] }],
    objections: [],
    created_at: "2026-11-01T12:00:00Z",
  } as unknown as Turn;
}

describe("the subtitle band", () => {
  it("names the speaker alongside what was said", () => {
    render(
      <SubtitleBand
        role="attacker_doctrinal"
        text="The rule does not apply."
      />,
    );

    const band = screen.getByTestId("subtitle-band");
    expect(band).toHaveTextContent("Doctrinal Counsel");
    expect(band).toHaveTextContent("The rule does not apply.");
  });

  it("says the court is silent rather than rendering an empty box", () => {
    render(<SubtitleBand role={null} text={null} />);

    expect(screen.getByTestId("subtitle-band")).toHaveTextContent(
      "The court is silent.",
    );
  });

  it("reserves its height so the scene does not jump between turns", () => {
    const { rerender } = render(
      <SubtitleBand role="presenter" text="Short." />,
    );
    const band = screen.getByTestId("subtitle-band");
    expect(band.className).toContain("min-h-[4.75rem]");

    // A long claim must be clamped, not allowed to grow the band. Without
    // this the courtroom above shifts up and down for the whole debate.
    rerender(
      <SubtitleBand role="presenter" text={"A very long claim. ".repeat(40)} />,
    );
    expect(band.querySelector("p")?.className).toContain("line-clamp-2");
  });

  it("is a live region, so a screen reader hears each turn", () => {
    render(<SubtitleBand role="judge" text="Objection overruled." />);

    expect(screen.getByTestId("subtitle-band")).toHaveAttribute(
      "aria-live",
      "polite",
    );
  });

  it("carries the speaking role's accent", () => {
    const { rerender } = render(<SubtitleBand role="presenter" text="x" />);
    expect(screen.getByTestId("subtitle-band").className).toContain(
      "border-l-bench-presenter",
    );

    rerender(<SubtitleBand role="judge" text="x" />);
    expect(screen.getByTestId("subtitle-band").className).toContain(
      "border-l-bench-judge",
    );
  });
});

describe("the bench layout", () => {
  /**
   * The nameplates in document order, which is left-to-right in the grid.
   *
   * Read off the sprites specifically — the band names the speaker too, so a
   * loose text query picks that up and the order depends on who last spoke.
   */
  function counselOrder(): (string | null)[] {
    return Array.from(document.querySelectorAll("[data-testid='sprite-plate']"))
      .map((el) => el.textContent)
      .filter((t) => t !== "The Bench");
  }

  it("seats doctrinal left, presenter centre, evidentiary right", () => {
    render(<Courtroom />);

    expect(counselOrder()).toEqual([
      "Doctrinal",
      "Presenting Counsel",
      "Evidentiary",
    ]);
  });

  it("keeps that order regardless of which role spoke first", () => {
    useCourtStore
      .getState()
      .addTurn(turn("attacker_evidentiary", "Evidence is thin."));
    render(<Courtroom />);

    expect(counselOrder()).toEqual([
      "Doctrinal",
      "Presenting Counsel",
      "Evidentiary",
    ]);
  });

  it("keeps the last thing said on screen while the next model generates", () => {
    // Presenting finishes; both attackers are now pending. The band must
    // still show the presenter's claim — a turn takes 40 to 90 seconds, and
    // blanking it would leave the band empty for most of the debate.
    useCourtStore
      .getState()
      .addTurn(turn("presenter", "The strike was lawful."));
    render(<Courtroom />);

    expect(useCourtStore.getState().pendingRoles).toContain(
      "attacker_doctrinal",
    );
    expect(screen.getByTestId("subtitle-band")).toHaveTextContent(
      "The strike was lawful.",
    );
  });
});

describe("role names", () => {
  it("gives each role a title, a sentence form, and a short plate", () => {
    expect(roleTitle("attacker_doctrinal")).toBe("Doctrinal Counsel");
    expect(roleSentence("attacker_doctrinal")).toBe("doctrinal counsel");
    expect(roleShort("attacker_doctrinal")).toBe("Doctrinal");
  });

  it("falls back to the raw id, so an unknown role is visible not blank", () => {
    expect(roleTitle("bailiff")).toBe("bailiff");
    expect(roleShort("bailiff")).toBe("bailiff");
  });
});
