import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import App from "@/App";
import { Courtroom } from "@/components/courtroom/Courtroom";
import { isLoud } from "@/components/courtroom/ObjectionFlourish";
import { SubtitleBand } from "@/components/courtroom/SubtitleBand";
import { roleSentence, roleShort, roleTitle } from "@/lib/roles";
import { useCourtStore } from "@/store/courtStore";
import type { Objection, Turn } from "@/types";

/**
 * Courtroom staging: the subtitle band and the bench layout.
 *
 * The band replaced a floating bubble and the counsel row became three
 * columns, so these assert the things that were wrong before — the speaker is
 * named, a long claim does not stretch the band, and the sprites sit in a
 * fixed order rather than wherever the turns arrived.
 */

function objection(
  raisedBy: Turn["role"],
  ground: string,
  grounded: boolean,
): Objection {
  return {
    id: `obj_${raisedBy}`,
    raised_by: raisedBy,
    ground,
    target_claim: "the claim",
    resolved_citations: grounded
      ? [
          {
            status: "resolved",
            citation: { type: "treaty", instrument: "gc_iv", article: "51" },
          },
        ]
      : [],
    disposition: "unaddressed",
  } as unknown as Objection;
}

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

describe("the objection flourish, localised", () => {
  /** The sprite wrapper an element sits inside, via its flex column. */
  function spriteOf(el: HTMLElement): HTMLElement {
    const sprite = el.closest("div.flex.flex-col");
    if (!sprite) throw new Error("no sprite ancestor");
    return sprite as HTMLElement;
  }

  it("bursts over the objecting sprite, not the courtroom", () => {
    const flourish = objection(
      "attacker_doctrinal",
      "Proportionality fails.",
      true,
    );
    expect(isLoud(flourish)).toBe(true);

    useCourtStore
      .getState()
      .addTurn(turn("presenter", "The strike was lawful."));
    useCourtStore.getState().showFlourish(flourish);
    render(<Courtroom />);

    const slam = screen.getByTestId("objection-slam");
    expect(
      within(spriteOf(slam)).getByTestId("sprite-plate"),
    ).toHaveTextContent("Doctrinal");
  });

  it("hangs from the outer corner, mirrored per bench", () => {
    // Doctrinal sits left of the room and evidentiary right, so the bursts
    // open outward and neither lands on the presenter between them.
    useCourtStore
      .getState()
      .showFlourish(
        objection("attacker_doctrinal", "Proportionality fails.", true),
      );
    const { unmount } = render(<Courtroom />);
    let slam = screen.getByTestId("objection-slam");
    expect(slam).toHaveAttribute("data-side", "left");
    // Asserts the side, not the exact offset: which corner it hangs from is
    // the behaviour, how far out it hangs is a tuning value.
    expect(slam.className).toMatch(/-left-\d/);
    expect(slam.className).not.toMatch(/-right-\d/);
    unmount();

    useCourtStore
      .getState()
      .showFlourish(objection("attacker_evidentiary", "Misquoted.", true));
    render(<Courtroom />);
    slam = screen.getByTestId("objection-slam");
    expect(slam).toHaveAttribute("data-side", "right");
    expect(slam.className).toMatch(/-right-\d/);
    expect(slam.className).not.toMatch(/-left-\d/);
  });

  it("puts the quiet tag on the same corner as the slam", () => {
    useCourtStore
      .getState()
      .showFlourish(objection("attacker_evidentiary", "Misquoted.", false));
    render(<Courtroom />);

    const quiet = screen.getByTestId("objection-quiet");
    expect(quiet).toHaveAttribute("data-side", "right");
    expect(quiet.className).toContain("-right-2");
  });

  it("leaves the other benches alone", () => {
    useCourtStore
      .getState()
      .showFlourish(
        objection("attacker_evidentiary", "The source is misquoted.", true),
      );
    render(<Courtroom />);

    const slam = screen.getByTestId("objection-slam");
    expect(
      within(spriteOf(slam)).getByTestId("sprite-plate"),
    ).toHaveTextContent("Evidentiary");
    // Exactly one burst: the previous version covered the whole scene, so
    // "which sprite" was not a question that could be asked.
    expect(screen.getAllByTestId("objection-slam")).toHaveLength(1);
  });

  it("reads the ground in the band, attributed to the raiser", () => {
    // The active role is the presenter — the band must still name the
    // objector, because an objection speaks for whoever raised it.
    useCourtStore
      .getState()
      .addTurn(turn("presenter", "The strike was lawful."));
    useCourtStore
      .getState()
      .showFlourish(
        objection("attacker_doctrinal", "Proportionality fails.", true),
      );
    render(<Courtroom />);

    const band = screen.getByTestId("subtitle-band");
    expect(band).toHaveTextContent("Doctrinal Counsel · Objection");
    expect(band).toHaveTextContent("Proportionality fails.");
    expect(band).not.toHaveTextContent("The strike was lawful.");
    expect(band.className).toContain("border-l-court-crimson");
  });

  it("shows a quiet tag, not a burst, for an ungrounded objection", () => {
    const flourish = objection(
      "attacker_evidentiary",
      "The source is misquoted.",
      false,
    );
    expect(isLoud(flourish)).toBe(false);

    useCourtStore.getState().showFlourish(flourish);
    render(<Courtroom />);

    expect(screen.queryByTestId("objection-slam")).not.toBeInTheDocument();
    const quiet = screen.getByTestId("objection-quiet");
    expect(
      within(spriteOf(quiet)).getByTestId("sprite-plate"),
    ).toHaveTextContent("Evidentiary");
    // Still reads in the band — only the burst is withheld.
    expect(screen.getByTestId("subtitle-band")).toHaveTextContent(
      "The source is misquoted.",
    );
  });

  it("keeps the objecting sprite lit even when another role is speaking", () => {
    // Without this the burst lands on a figure already dimmed to 45%.
    useCourtStore
      .getState()
      .addTurn(turn("presenter", "The strike was lawful."));
    useCourtStore
      .getState()
      .showFlourish(
        objection("attacker_doctrinal", "Proportionality fails.", true),
      );
    render(<Courtroom />);

    const sprite = spriteOf(screen.getByTestId("objection-slam"));
    // Lit is full brightness and full saturation. Not opacity: an inactive
    // sprite is darkened rather than faded, because a translucent figure let
    // the drawn chamber show through it.
    expect(sprite.className).toContain("brightness-100");
    expect(sprite.className).not.toContain("brightness-75");
  });
});


describe("the chamber", () => {
  it("draws the room behind the sprites", () => {
    render(<Courtroom />);

    const chamber = screen.getByTestId("chamber");
    // Decorative: it must not be announced, and nothing in it carries
    // information the transcript does not also state.
    expect(chamber).toHaveAttribute("aria-hidden");
    expect(chamber.tagName.toLowerCase()).toBe("svg");
  });

  it("stretches instead of imposing an aspect ratio", () => {
    render(<Courtroom />);

    // The reason it is drawn rather than photographed: the panel has to grow
    // with its content, so the room cannot dictate the layout.
    expect(screen.getByTestId("chamber")).toHaveAttribute("preserveAspectRatio", "none");
  });

  it("is painted in theme tokens, so it follows the palette", () => {
    render(<Courtroom />);

    // A fixed image cannot do this, which is the whole argument for the SVG:
    // every fill reads a custom property rather than a literal colour.
    const markup = screen.getByTestId("chamber").innerHTML;
    expect(markup).toContain("var(--court-gold)");
    expect(markup).toContain("var(--court-rail)");
    expect(markup).toContain("var(--court-ink)");
    expect(markup).not.toMatch(/#[0-9a-f]{6}/i);
  });

  it("keeps the figures opaque and in front of the room", () => {
    render(<Courtroom />);

    // The chamber showed through the sprites: the seal behind the bench
    // appeared inside the judge's head, and floor boards ran through the
    // nameplates. Both are solved the same way — opaque fill, raised above
    // the drawing — so both are pinned here.
    for (const plate of screen.getAllByTestId("sprite-plate")) {
      const box = plate.parentElement as HTMLElement;
      expect(box.className).toContain("bg-court-ink");
      // An alpha suffix on the fill is what let the room through.
      expect(box.className).not.toMatch(/bg-court-ink\//);
      // Above the room, whichever layer that takes: counsel's plates clear
      // the chamber, the judge's also has to clear the bench.
      expect(box.className).toMatch(/\bz-(10|20|30)\b/);
    }
  });

  it("paints the furniture opaquely, so it does not tint what it covers", () => {
    render(<Courtroom />);

    // The bench greyed out because it filled with translucent `ink` while
    // sitting over the judge's dark brown plinth — a light tan at 60-86%
    // over dark brown composites to a wash, and because the gradient
    // crossed the figure's edge the bench came out two colours with a seam
    // down the middle. A solid object is one colour whatever is behind it.
    for (const id of ["judge-bench", "presenter-stand"]) {
      const markup = screen.getByTestId(id).innerHTML;
      expect(markup).toContain("color-mix");
      // `fill-opacity` on a wood fill is the bug returning.
      expect(markup).not.toMatch(/fill-opacity="0\.[0-9]+"[^>]*url\(#/);
    }
  });

  it("confines the room to the scene, not the whole panel", () => {
    render(<Courtroom />);

    // The furniture stretches to `inset-0` of its container, and its 240
    // vertical units are mapped onto that container's height. When it was
    // the whole section, the rail landed at 77.5% of a box that also held
    // the caption and the corner readout -- so the banisters cut through
    // the caption text and the round indicator sat inside the panelling.
    const scene = screen.getByTestId("chamber").parentElement as HTMLElement;
    expect(scene.contains(screen.getByTestId("gallery-rail"))).toBe(true);
    // The caption and the corner readout live outside it.
    expect(scene.textContent).not.toContain("not in session");
  });

  it("keeps the courtroom out of the column the dissent log toggles", () => {
    render(<App />);

    // The scene stretches to whatever width it is given, over a box of
    // fixed height, so any container that changes width changes where the
    // furniture lands relative to the figures. The dissent log opening is
    // such a change -- it must not reach the courtroom.
    const scene = screen.getByTestId("chamber").parentElement as HTMLElement;
    const toggling = scene.closest('[class*="lg:grid-cols-"]');
    expect(toggling).toBeNull();
  });

  it("gives the scene a bounded height, not one tied to its width", () => {
    render(<Courtroom />);

    // The room draws with preserveAspectRatio="none" so it can stretch.
    // Tying the scene box to the room's 5/3 ratio instead made a wide
    // panel over 1000px tall -- past the viewport, with the furniture
    // scattered away from the figures it belongs to.
    const scene = screen.getByTestId("chamber").parentElement as HTMLElement;
    expect(scene.className).not.toMatch(/aspect-/);
    expect(scene.className).toMatch(/\bh-\[/);
  });

  it("keeps the nameplates out from under the furniture", () => {
    render(<Courtroom />);

    // Every plate that sat under its figure ended up behind woodwork --
    // the bench across the judge, the rail across counsel, both opaque.
    // Beside the figure there is nothing in front of them.
    for (const plate of screen.getAllByTestId("sprite-plate")) {
      const box = plate.parentElement as HTMLElement;
      expect(box.className).toMatch(/\b(left-full|right-full)\b/);
      expect(box.className).toContain("absolute");
    }
  });

  it("stacks the bench, the lectern and the rail over the figures", () => {
    render(<Courtroom />);

    // The judge rising from behind the bench is the whole reason the
    // furniture is a separate layer rather than part of the back drawing.
    // If these ever render inside `chamber` again the stacking silently
    // inverts and the judge sits on top of the bench, which is what it
    // looked like before.
    const chamber = screen.getByTestId("chamber");
    for (const id of ["judge-bench", "presenter-stand", "gallery-rail"]) {
      expect(chamber.contains(screen.getByTestId(id))).toBe(false);
    }
    // The rail divides the court from the gallery, which only reads if it
    // crosses in front of counsel.
    expect(screen.getByTestId("gallery-rail").getAttribute("class")).toContain("z-20");
    // The bench paints over the judge -- that is the whole reason the
    // furniture is a separate layer. If it ever renders inside `chamber`
    // again the stacking silently inverts and the judge sits on top of it.
    expect(screen.getByTestId("judge-bench").getAttribute("class")).toContain("z-20");
    // The lectern goes behind: the presenter must be fully visible, and in
    // front it crossed the face and the role's letter.
    expect(screen.getByTestId("presenter-stand").getAttribute("class")).toContain("z-0");
  });

  it("does not fade an inactive figure to translucent", () => {
    render(<Courtroom />);

    // An unlit sprite is out of the light, not half-absent. Opacity here let
    // the drawn room show through whoever was not speaking.
    const plate = screen.getAllByTestId("sprite-plate")[0];
    const sprite = plate.closest("div")?.parentElement as HTMLElement;
    expect(sprite.className).not.toMatch(/\bopacity-\d/);
  });
});
