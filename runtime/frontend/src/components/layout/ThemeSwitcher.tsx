import { useState } from "react";

import {
  ALTERNATE_THEME,
  applyTheme,
  DEFAULT_THEME,
  storedTheme,
  THEME_LABELS,
  THEMES,
  type ThemeName,
} from "@/styles/themes";

/**
 * Toggles between the two courtroom palettes.
 *
 * One button rather than a row of swatches: there are two palettes, Oak for
 * daylight and Dusk for dark, so a picker would be a list of length two. It
 * shows where it is going, not where it is — a control labelled with the
 * current state reads as a status display.
 *
 * The change arrives as a wave out of this button. See `theme-wave` in
 * index.css for the mechanism; this supplies the origin, because only the
 * button knows where it is on the page.
 */

/** A View Transition, where the browser has them. */
type WithViewTransition = Document & {
  startViewTransition?: (cb: () => void) => { finished: Promise<void> };
};

export function ThemeSwitcher() {
  const [current, setCurrent] = useState<ThemeName>(storedTheme);

  const next = current === DEFAULT_THEME ? ALTERNATE_THEME : DEFAULT_THEME;

  const toggle = (event: React.MouseEvent<HTMLButtonElement>) => {
    const root = document.documentElement;

    // Centre the wave on the button, and give it a radius that reaches the
    // furthest corner — a fixed radius would leave a corner unpainted when
    // the button is inset, or overshoot wildly when it is central.
    const box = event.currentTarget.getBoundingClientRect();
    const x = box.left + box.width / 2;
    const y = box.top + box.height / 2;
    const reach = Math.hypot(
      Math.max(x, window.innerWidth - x),
      Math.max(y, window.innerHeight - y),
    );
    root.style.setProperty("--wave-x", `${x}px`);
    root.style.setProperty("--wave-y", `${y}px`);
    root.style.setProperty("--wave-r", `${Math.ceil(reach)}px`);

    const apply = () => {
      applyTheme(next);
      setCurrent(next);
    };

    // Without the API the switch still happens, just instantly. Checked at
    // the call site rather than polyfilled: a palette change that does not
    // animate is a complete outcome, not a degraded one.
    const doc = document as WithViewTransition;
    if (typeof doc.startViewTransition !== "function") {
      apply();
      return;
    }
    doc.startViewTransition(apply);
  };

  const theme = THEMES[next];

  return (
    <button
      data-testid="theme-switcher"
      type="button"
      onClick={toggle}
      // The accessible name says what pressing it does; `data-theme` on <html>
      // is what a test or a stylesheet reads for the current palette.
      aria-label={`Switch to the ${THEME_LABELS[next]} palette`}
      title={`Switch to ${THEME_LABELS[next]}`}
      className="flex items-center gap-1.5 rounded border border-court-rail px-2 py-1 font-ui text-[11px] text-court-fg/55 transition hover:border-court-gold/40 hover:text-court-fg/80"
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
      {THEME_LABELS[next]}
    </button>
  );
}
