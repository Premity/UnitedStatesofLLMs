/**
 * Courtroom palettes.
 *
 * The theme is applied as CSS custom properties on <html>, and Tailwind's
 * colour tokens read those variables — so switching is a runtime change, not a
 * rebuild. That exists so the palette can be chosen by looking at it rather
 * than by reading hex codes.
 *
 * Every theme defines the same keys. Tailwind cannot warn about a missing one,
 * so `Theme` is a closed record and a new palette will not compile until it
 * sets them all.
 *
 * Two registers throughout: a courtroom for the live proceeding and a sober
 * record for the dissent log. The record stays close to paper in every theme —
 * it is the part that gets printed and handed to someone.
 */

export interface Theme {
  /** Page ground, panels, hairlines, the deepest ink. */
  bg: string;
  panel: string;
  rail: string;
  ink: string;
  /**
   * Text on the courtroom's ground.
   *
   * A token rather than a hardcoded white, so a theme can put a dark
   * courtroom on a light ground. Components use `text-court-fg/70` and the
   * like; the alpha steps still work because the variable holds channels.
   */
  fg: string;
  /**
   * Which way round this theme reads. Drives `color-scheme`, so form controls
   * and scrollbars match, and lets a component pick a contrasting fill where
   * one is genuinely needed.
   */
  scheme: "dark" | "light";
  /** The accent: bench fittings, headings, the primary control. */
  gold: string;
  /**
   * Text on a gold fill — the primary button's label.
   *
   * Its own token because it has to contrast with gold, not with the page.
   * It was `ink`, which also means "a surface recessed below the panel";
   * those two jobs pull opposite ways once a theme is light.
   */
  onGold: string;
  /** Objections and errors, as text on the page. */
  crimson: string;
  /**
   * Crimson as a *fill* — the objection burst.
   *
   * Separate from `crimson` because the two pull opposite ways: crimson has
   * to be light enough to read as small text on a dark panel, while a fill
   * carrying light prose has to be dark enough for that prose. One token
   * cannot satisfy both.
   */
  crimsonDeep: string;
  /** Per-role bench colours, used by the sprites and the transcript rules. */
  benchPresenter: string;
  benchDoctrinal: string;
  benchEvidentiary: string;
  benchJudge: string;
  /** The record: a light surface inside a dark app. */
  paper: string;
  recordInk: string;
  recordRule: string;
  recordMargin: string;
}

export const THEMES = {
  /**
   * Oak. A daylit courtroom: light tan ground, walnut accents, oxblood for
   * objections — panelled wood and morning light rather than a dark room.
   *
   * The only light theme, which is why `fg` and `scheme` exist: every other
   * palette assumed white text on a dark ground.
   *
   * One trade-off worth knowing. In the dark themes the record reads as a
   * bright page against a dark room — roughly 12:1 — and that contrast is
   * most of what separates the proceeding from the record. Here both are
   * light and the ratio falls to about 1.2:1, so the separation has to come
   * from the record's border and shadow instead. That is why `paper` is kept
   * near-white rather than another tan: it is the most distinction available
   * once both registers are light.
   */
  oak: {
    bg: "#ede0cc",
    fg: "#33251a",
    scheme: "light",
    panel: "#e2d2b8",
    rail: "#c4ad8c",
    // `ink` is "a surface recessed below the panel" — input fields, the sprite
    // caption — and is also the label on the gold button, so it has to read
    // against gold as well as against the panel. A deeper tan, not a lighter
    // one: inverting it would make the inputs float above the form.
    ink: "#d2bb98",
    gold: "#7a4a20",
    onGold: "#fbf7ee",
    crimson: "#9e2f2f",
    crimsonDeep: "#8f2525",
    benchPresenter: "#3c6470",
    benchDoctrinal: "#9e2f2f",
    benchEvidentiary: "#a35a22",
    benchJudge: "#7a4a20",
    paper: "#fbf7ee",
    recordInk: "#241a12",
    recordRule: "#d8c7a8",
    recordMargin: "#7d6244",
  },
  /** The original. Deep violet dusk — reads more game than courtroom. */
  dusk: {
    bg: "#1a1229",
    fg: "#ffffff",
    scheme: "dark",
    panel: "#241a3a",
    rail: "#3b2a5c",
    ink: "#0f0a1a",
    gold: "#e8b84b",
    onGold: "#0f0a1a",
    crimson: "#e4647a",
    crimsonDeep: "#a8203a",
    benchPresenter: "#3d7ea6",
    benchDoctrinal: "#c2384a",
    benchEvidentiary: "#c56a30",
    benchJudge: "#e8b84b",
    paper: "#f7f3e9",
    recordInk: "#1f1a14",
    recordRule: "#d9d0bd",
    recordMargin: "#8a7a5c",
  },
} as const satisfies Record<string, Theme>;

export type ThemeName = keyof typeof THEMES;

export const THEME_NAMES = Object.keys(THEMES) as ThemeName[];

export const THEME_LABELS: Record<ThemeName, string> = {
  oak: "Oak",
  dusk: "Dusk",
};

/** Maps a theme key to the CSS custom property Tailwind reads. */
const VARIABLE: Record<Exclude<keyof Theme, "scheme">, string> = {
  bg: "--court-bg",
  panel: "--court-panel",
  rail: "--court-rail",
  ink: "--court-ink",
  fg: "--court-fg",
  gold: "--court-gold",
  onGold: "--court-on-gold",
  crimson: "--court-crimson",
  crimsonDeep: "--court-crimson-deep",
  benchPresenter: "--bench-presenter",
  benchDoctrinal: "--bench-doctrinal",
  benchEvidentiary: "--bench-evidentiary",
  benchJudge: "--bench-judge",
  paper: "--record-paper",
  recordInk: "--record-ink",
  recordRule: "--record-rule",
  recordMargin: "--record-margin",
};

const STORAGE_KEY = "council:theme";

/**
 * Oak, the daylit courtroom. Dusk is the dark counterpart and the only other
 * palette — three further experiments (Chambers, Ember, Tribunal) were cut
 * once this one was settled, since every theme is a set of contrast ratios to
 * keep honest and two is the pair worth maintaining.
 */
export const DEFAULT_THEME: ThemeName = "oak";

/** The theme the toggle switches to from the default, and back. */
export const ALTERNATE_THEME: ThemeName = "dusk";

/**
 * "#d9a441" -> "217 164 65".
 *
 * Tailwind composes opacity modifiers as `rgb(var(--x) / <alpha>)`, which only
 * works when the variable holds bare channels. Themes are written as hex
 * because that is what anyone picking colours reads.
 */
function channels(hex: string): string {
  return [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)).join(" ");
}

/** Writes a theme's variables onto the document root. */
export function applyTheme(name: ThemeName): void {
  const theme = THEMES[name];
  const root = document.documentElement;

  for (const [key, variable] of Object.entries(VARIABLE)) {
    root.style.setProperty(
      variable,
      channels(theme[key as keyof typeof VARIABLE]),
    );
  }

  root.dataset.theme = name;
  // Form controls and scrollbars follow this; without it a light theme gets
  // dark native widgets.
  root.style.colorScheme = theme.scheme;

  // A preference, not state the app depends on — a blocked or full store is
  // not an error, it just means the choice does not survive a reload.
  try {
    localStorage.setItem(STORAGE_KEY, name);
  } catch {
    /* ignore */
  }
}

/** The stored preference, or the default when there is none or it is stale. */
export function storedTheme(): ThemeName {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved && saved in THEMES) return saved as ThemeName;
  } catch {
    /* ignore */
  }
  return DEFAULT_THEME;
}
