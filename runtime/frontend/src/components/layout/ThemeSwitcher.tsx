import { useCallback, useRef, useState } from "react";

import {
  ALTERNATE_THEME,
  applyTheme,
  DEFAULT_THEME,
  storedTheme,
  THEMES,
  THEME_LABELS,
  type ThemeName,
} from "@/styles/themes";

/**
 * Day/night toggle: a sun that flips to a moon, and a wave out of the button.
 *
 * One control rather than a picker, because there are two palettes. The face
 * shows the palette being offered, not the current one — a button labelled
 * with the state it is already in reads as a status display.
 *
 * The wave is a View Transition. See `theme-wave` in index.css for why it has
 * to be one and not an element of our own; this supplies the origin, because
 * only the button knows where it is on the page.
 *
 * Spammable. A browser runs one view transition at a time, so a click during
 * a running wave cannot overlap it — it interrupts instead, finishing the
 * current palette immediately and starting a fresh wave from the same button.
 * Every click is honoured and every click produces a visible sweep; what it
 * does not do is paint two sweeps at once, which the platform will not allow.
 */

/** A View Transition, where the browser has them. */
type WithViewTransition = Document & {
  startViewTransition?: (cb: () => void) => {
    finished: Promise<void>;
    skipTransition: () => void;
  };
};

export function ThemeSwitcher() {
  const [current, setCurrent] = useState<ThemeName>(storedTheme);

  /**
   * The palette the last click is heading for, which during a wave is not yet
   * the one on screen.
   *
   * Each click flips from the previous click's target rather than from the
   * live theme, so a second click mid-wave goes somewhere new instead of
   * re-applying what is already arriving.
   */
  const queuedRef = useRef(current);

  /** The wave in flight, so the next click can cut it short. */
  const runningRef = useRef<{ skipTransition: () => void } | null>(null);

  const next = current === DEFAULT_THEME ? ALTERNATE_THEME : DEFAULT_THEME;

  const toggle = useCallback((event: React.MouseEvent<HTMLButtonElement>) => {
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

    const target =
      queuedRef.current === DEFAULT_THEME ? ALTERNATE_THEME : DEFAULT_THEME;
    queuedRef.current = target;

    const apply = () => {
      applyTheme(target);
      setCurrent(target);
    };

    // Without the API the switch still happens, just instantly. Checked at
    // the call site rather than polyfilled: a palette change that does not
    // animate is a complete outcome, not a degraded one.
    const doc = document as WithViewTransition;
    if (typeof doc.startViewTransition !== "function") {
      apply();
      return;
    }

    // Cut the previous wave short so this click gets its own from the start.
    // Without this the browser drops the new transition on the floor and a
    // fast second click changes the palette with no animation at all.
    runningRef.current?.skipTransition();

    const transition = doc.startViewTransition(apply);
    runningRef.current = transition;
    void transition.finished.then(() => {
      if (runningRef.current === transition) runningRef.current = null;
    });
  }, []);

  return (
    <button
      data-testid="theme-switcher"
      type="button"
      onClick={toggle}
      // The name says what pressing it does; `data-theme` on <html> is what a
      // test or a stylesheet reads for the palette in force.
      aria-label={`Switch to the ${THEME_LABELS[next]} palette`}
      title={`Switch to ${THEME_LABELS[next]}`}
      className="flex items-center gap-1.5 rounded border border-court-rail px-2 py-1 font-ui text-[11px] text-court-fg/55 transition hover:border-court-gold/40 hover:text-court-fg/80"
    >
      {/* The coin needs the depth on the wrapper, not on the spinning face. */}
      <span aria-hidden className="grid h-4 w-4 place-items-center [perspective:300px]">
        <span
          data-testid="theme-coin"
          data-face={THEMES[next].scheme}
          className="coin relative grid h-4 w-4 place-items-center"
        >
          <span className="coin-face absolute text-court-gold" data-side="front">
            <SunIcon />
          </span>
          <span className="coin-face absolute text-court-gold" data-side="back">
            <MoonIcon />
          </span>
        </span>
      </span>
      {THEME_LABELS[next]}
    </button>
  );
}

function SunIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden className="h-4 w-4" fill="none">
      <circle cx="12" cy="12" r="4.2" fill="currentColor" />
      {Array.from({ length: 8 }, (_, i) => {
        const a = (i / 8) * Math.PI * 2;
        return (
          <line
            key={i}
            x1={12 + 6.6 * Math.cos(a)}
            y1={12 + 6.6 * Math.sin(a)}
            x2={12 + 9.2 * Math.cos(a)}
            y2={12 + 9.2 * Math.sin(a)}
            stroke="currentColor"
            strokeWidth="1.9"
            strokeLinecap="round"
          />
        );
      })}
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden className="h-4 w-4">
      {/* A crescent as one path: a disc with a bite taken out, rather than two
          overlapping circles, which would show the seam on a coloured fill. */}
      <path d="M20 14.5A8.5 8.5 0 1 1 11.2 3a7 7 0 0 0 8.8 11.5Z" fill="currentColor" />
    </svg>
  );
}
