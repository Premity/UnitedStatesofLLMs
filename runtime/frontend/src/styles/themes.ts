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
  /** The accent: bench fittings, headings, the primary control. */
  gold: string;
  /** Objections and errors. */
  crimson: string;
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
  /** The original. Deep violet dusk — reads more game than courtroom. */
  dusk: {
    bg: "#1a1229",
    panel: "#241a3a",
    rail: "#3b2a5c",
    ink: "#0f0a1a",
    gold: "#e8b84b",
    crimson: "#c2384a",
    benchPresenter: "#3d7ea6",
    benchDoctrinal: "#c2384a",
    benchEvidentiary: "#d4763a",
    benchJudge: "#e8b84b",
    paper: "#f7f3e9",
    recordInk: "#1f1a14",
    recordRule: "#d9d0bd",
    recordMargin: "#8a7a5c",
  },

  /**
   * Oxblood and leather. Warm, archival — a law library after hours.
   * The record's parchment already sits in this family.
   */
  chambers: {
    bg: "#1c1210",
    panel: "#2a1c18",
    rail: "#4a3028",
    ink: "#0f0908",
    gold: "#d9a441",
    crimson: "#b33a3a",
    benchPresenter: "#4a7c7e",
    benchDoctrinal: "#b33a3a",
    benchEvidentiary: "#c67a3e",
    benchJudge: "#d9a441",
    paper: "#f5efe2",
    recordInk: "#1f1813",
    recordRule: "#ddd2bc",
    recordMargin: "#8a7656",
  },

  /**
   * Slate and navy. Institutional and cool — closest to a real court's
   * sobriety, and the least decorative of the three.
   */
  tribunal: {
    bg: "#0f172a",
    panel: "#1a2436",
    rail: "#2e3f58",
    ink: "#070c16",
    gold: "#d6b068",
    crimson: "#c0455a",
    benchPresenter: "#4b86b4",
    benchDoctrinal: "#c0455a",
    benchEvidentiary: "#cf8b4a",
    benchJudge: "#d6b068",
    paper: "#f4f2ec",
    recordInk: "#161b22",
    recordRule: "#d5d2c8",
    recordMargin: "#7d7b70",
  },
} as const satisfies Record<string, Theme>;

export type ThemeName = keyof typeof THEMES;

export const THEME_NAMES = Object.keys(THEMES) as ThemeName[];

export const THEME_LABELS: Record<ThemeName, string> = {
  dusk: "Dusk",
  chambers: "Chambers",
  tribunal: "Tribunal",
};

/** Maps a theme key to the CSS custom property Tailwind reads. */
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

const STORAGE_KEY = "council:theme";

export const DEFAULT_THEME: ThemeName = "chambers";

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
    root.style.setProperty(variable, channels(theme[key as keyof Theme]));
  }
  root.dataset.theme = name;

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
