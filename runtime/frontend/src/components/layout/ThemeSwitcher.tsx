import { useState } from "react";

import {
  applyTheme,
  storedTheme,
  THEMES,
  THEME_LABELS,
  THEME_NAMES,
  type ThemeName,
} from "@/styles/themes";

/**
 * Picks a courtroom palette.
 *
 * Exists so the palette can be chosen by looking at the running courtroom
 * rather than by reading hex codes. Each option carries a swatch of the three
 * colours that actually distinguish the themes — ground, accent, objection.
 *
 * Whether this survives the design decision is an open question: once a
 * palette is settled it may be better as a fixed theme than a visible control.
 */
export function ThemeSwitcher() {
  const [current, setCurrent] = useState<ThemeName>(storedTheme);

  const choose = (name: ThemeName) => {
    applyTheme(name);
    setCurrent(name);
  };

  return (
    <div
      data-testid="theme-switcher"
      role="group"
      aria-label="Courtroom palette"
      className="flex items-center gap-1"
    >
      {THEME_NAMES.map((name) => {
        const theme = THEMES[name];
        const active = name === current;

        return (
          <button
            key={name}
            type="button"
            onClick={() => choose(name)}
            aria-pressed={active}
            title={THEME_LABELS[name]}
            className={`flex items-center gap-1.5 rounded border px-2 py-1 font-ui text-[11px] transition ${
              active
                ? "border-court-gold/60 bg-court-gold/10 text-court-gold"
                : "border-court-rail text-white/45 hover:border-court-gold/30 hover:text-white/70"
            }`}
          >
            <span aria-hidden className="flex overflow-hidden rounded-sm">
              {[theme.bg, theme.gold, theme.crimson].map((colour) => (
                <span
                  key={colour}
                  style={{ background: colour }}
                  className="h-3 w-2"
                />
              ))}
            </span>
            {THEME_LABELS[name]}
          </button>
        );
      })}
    </div>
  );
}
