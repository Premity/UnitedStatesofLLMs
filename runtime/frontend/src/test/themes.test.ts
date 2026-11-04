import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { beforeEach, describe, expect, it } from "vitest";

import {
  applyTheme,
  DEFAULT_THEME,
  storedTheme,
  THEMES,
  THEME_LABELS,
  THEME_NAMES,
  type Theme,
} from "@/styles/themes";

const KEYS = Object.keys(THEMES.dusk) as (keyof Theme)[];

describe("the palettes", () => {
  it("define every key, so no theme is half-applied", () => {
    for (const name of THEME_NAMES) {
      expect(Object.keys(THEMES[name]).sort()).toEqual([...KEYS].sort());
    }
  });

  it("are all valid six-digit hex", () => {
    for (const name of THEME_NAMES) {
      for (const key of KEYS) {
        expect(THEMES[name][key]).toMatch(/^#[0-9a-f]{6}$/);
      }
    }
  });

  it("names a label for each", () => {
    expect(Object.keys(THEME_LABELS).sort()).toEqual([...THEME_NAMES].sort());
  });

  /**
   * Relative luminance, per WCAG 2.1. Kept here rather than pulled in as a
   * dependency: it is six lines and only the tests need it.
   */
  const luminance = (hex: string) => {
    const channels = [1, 3, 5]
      .map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
      .map((v) => (v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
  };

  const contrast = (a: string, b: string) => {
    const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
    return (hi + 0.05) / (lo + 0.05);
  };

  // The objection styles put 10–11px text directly on crimson, and headings
  // and the primary control on gold, so both have to clear AA (4.5:1) against
  // the panel they sit on. A palette that fails this is unreadable, not just
  // ugly — which is easy to miss when choosing colours by eye.
  it.each(THEME_NAMES)("%s keeps its accents readable on the panel", (name) => {
    const theme = THEMES[name];
    expect(contrast(theme.crimson, theme.panel)).toBeGreaterThanOrEqual(4.5);
    expect(contrast(theme.gold, theme.panel)).toBeGreaterThanOrEqual(4.5);
  });

  it.each(THEME_NAMES)("%s keeps the record legible", (name) => {
    const theme = THEMES[name];
    expect(contrast(theme.recordInk, theme.paper)).toBeGreaterThanOrEqual(4.5);
  });
});

describe("applying a theme", () => {
  beforeEach(() => {
    document.documentElement.removeAttribute("style");
    localStorage.clear();
  });

  it("writes bare RGB channels, which is what Tailwind's alpha needs", () => {
    applyTheme("chambers");

    const root = document.documentElement;
    // #d9a441 -> 217 164 65. A hex value here would silently break every
    // opacity modifier in the app.
    expect(root.style.getPropertyValue("--court-gold")).toBe("217 164 65");
    expect(root.dataset.theme).toBe("chambers");
  });

  it("remembers the choice and reads it back", () => {
    applyTheme("tribunal");
    expect(storedTheme()).toBe("tribunal");
  });

  it("falls back to the default when nothing is stored", () => {
    expect(storedTheme()).toBe(DEFAULT_THEME);
  });

  it("ignores a stored value that is no longer a theme", () => {
    localStorage.setItem("council:theme", "midnight-disco");
    expect(storedTheme()).toBe(DEFAULT_THEME);
  });
});

describe("the stylesheet's default palette", () => {
  // index.css carries the default theme so the page is styled before any JS
  // runs, and so raw rgb(var(--x)) uses outside Tailwind resolve. That is a
  // hand-kept copy of one theme, so assert it has not drifted.
  // Resolved from the project root: under jsdom `import.meta.url` is not a
  // file URL, and vitest runs with the project root as cwd.
  const css = readFileSync(resolve("src/styles/index.css"), "utf8");

  const toChannels = (hex: string) =>
    [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)).join(" ");

  const VARIABLE: Record<keyof Theme, string> = {
    bg: "--court-bg",
    panel: "--court-panel",
    rail: "--court-rail",
    ink: "--court-ink",
    gold: "--court-gold",
    crimson: "--court-crimson",
    benchPresenter: "--bench-presenter",
    benchDoctrinal: "--bench-doctrinal",
    benchEvidentiary: "--bench-evidentiary",
    benchJudge: "--bench-judge",
    paper: "--record-paper",
    recordInk: "--record-ink",
    recordRule: "--record-rule",
    recordMargin: "--record-margin",
  };

  it.each(KEYS)("matches THEMES.%s for the default theme", (key) => {
    const expected = toChannels(THEMES[DEFAULT_THEME][key]);
    expect(css).toContain(`${VARIABLE[key]}: ${expected};`);
  });
});
