/**
 * The room the proceeding happens in, drawn rather than photographed.
 *
 * A courtroom is recognised from its furniture in perspective, not from its
 * walls: the raised bench as a solid mass, a rail across the well, counsel
 * tables, a floor going away from you. An earlier pass drew a panelled
 * elevation and read as striped wallpaper — flat, no depth, nothing a person
 * could stand in.
 *
 * Drawn in SVG rather than photographed for three reasons a fixed image
 * fails:
 *
 * - **It follows the palette.** Every fill is a theme token, so the room is
 *   oak and daylight under Oak and deep violet under Dusk. A photograph that
 *   suits one fights the other, and the default is the light one.
 * - **It has no aspect ratio.** `preserveAspectRatio="none"` lets the panel
 *   grow with its content, so the courtroom does not dictate the layout.
 * - **It costs a few KB** and needs no licence, which the two images proposed
 *   for this did (both © Capcom; see ISSUES.md).
 *
 * The viewBox is 400×240 and the furniture is placed against where the
 * sprites actually land: the judge around y=40, counsel around y=150. Those
 * are percentages of a stretched box, so they hold as the panel resizes.
 *
 * Decorative: `aria-hidden`, and nothing here carries information the
 * transcript does not also state.
 */
export function Chamber() {
  return (
    <svg
      aria-hidden
      data-testid="chamber"
      viewBox="0 0 400 240"
      preserveAspectRatio="none"
      className="pointer-events-none absolute inset-0 h-full w-full"
    >
      <defs>
        {/* Light from above the bench, falling off toward the gallery. */}
        <radialGradient id="chamber-light" cx="0.5" cy="0.1" r="0.9">
          <stop offset="0%" stopColor="rgb(var(--court-gold))" stopOpacity="0.1" />
          <stop offset="100%" stopColor="rgb(var(--court-ink))" stopOpacity="0.28" />
        </radialGradient>

        {/* Wood for the solids.

            `--court-ink` is the recessed surface in both palettes — a deep
            tan under Oak, near-black under Dusk — so leaning on it is what
            makes the furniture read as an object against the ground either
            way round.

            The fill alone is not enough, though: under Dusk `ink` and `bg`
            are both near-black, so any mix of them lands around 1.05:1 and
            the bench disappears. What carries the shape in both palettes is
            the gold edge on every solid — an outline reads where a fill
            cannot. Measured, not assumed; see the chamber contrast test. */}
        <linearGradient id="chamber-wood" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="rgb(var(--court-ink))" stopOpacity="0.55" />
          <stop offset="100%" stopColor="rgb(var(--court-ink))" stopOpacity="0.8" />
        </linearGradient>

        {/* The floor recedes, so it is lighter at the back where the light is. */}
        <linearGradient id="chamber-floor" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="rgb(var(--court-ink))" stopOpacity="0.18" />
          <stop offset="100%" stopColor="rgb(var(--court-ink))" stopOpacity="0.42" />
        </linearGradient>
      </defs>

      <rect width="400" height="240" fill="url(#chamber-light)" />

      {/* --- Back wall, with the only panelling that stays: tall and narrow,
              behind the bench, where it reads as a room end rather than as a
              repeating texture across the whole width. --- */}
      <rect width="400" height="96" fill="rgb(var(--court-ink))" fillOpacity="0.16" />
      {[52, 92, 308, 348].map((x) => (
        <rect
          key={x}
          x={x}
          y="14"
          width="26"
          height="68"
          rx="2"
          fill="rgb(var(--court-rail))"
          fillOpacity="0.16"
        />
      ))}

      {/* The seal behind the bench: a disc and a suggestion of scales. One
          emblem says "court" faster than any amount of panelling. */}
      <g opacity="0.6">
        <circle
          cx="200"
          cy="44"
          r="25"
          fill="none"
          stroke="rgb(var(--court-gold))"
          strokeWidth="1.5"
        />
        <circle
          cx="200"
          cy="44"
          r="19"
          fill="none"
          stroke="rgb(var(--court-gold))"
          strokeWidth="0.75"
        />
        <path
          d="M200 32 L200 56 M188 38 L212 38 M186 38 L182 47 M190 38 L194 47 M210 38 L206 47 M214 38 L218 47"
          stroke="rgb(var(--court-gold))"
          strokeWidth="1.25"
          fill="none"
          strokeLinecap="round"
        />
        <path d="M192 56 L208 56" stroke="rgb(var(--court-gold))" strokeWidth="2" />
      </g>

      {/* --- The floor, in perspective. Converging edges are what turn an
              elevation into a room. --- */}
      <path d="M0 240 L96 96 L304 96 L400 240 Z" fill="url(#chamber-floor)" />
      {/* Boards, converging on the same vanishing point as the walls. */}
      {[-180, -90, 0, 90, 180].map((offset) => (
        <path
          key={offset}
          d={`M${200 + offset * 1.8} 240 L${200 + offset * 0.42} 96`}
          stroke="rgb(var(--court-ink))"
          strokeOpacity="0.14"
          strokeWidth="1"
        />
      ))}

      {/* --- The judge's bench: a solid mass the judge sits behind, raised on
              a plinth. This is the single most recognisable object in the
              room, so it is the most opaque thing drawn. --- */}
      <g>
        {/* Plinth, wider than the bench and set below it. */}
        <path
          d="M132 92 L268 92 L276 112 L124 112 Z"
          fill="rgb(var(--court-ink))"
          fillOpacity="0.45"
          stroke="rgb(var(--court-gold))"
          strokeOpacity="0.55"
          strokeWidth="1"
        />
        {/* The bench front. */}
        <rect
          x="138"
          y="58"
          width="124"
          height="36"
          rx="2"
          fill="url(#chamber-wood)"
          stroke="rgb(var(--court-gold))"
          strokeOpacity="0.8"
          strokeWidth="1.25"
        />
        {/* Its lip, which catches the light. */}
        <rect
          x="134"
          y="54"
          width="132"
          height="6"
          rx="2"
          fill="rgb(var(--court-gold))"
          fillOpacity="0.6"
        />
        {/* Two recessed panels on the front, so it reads as joinery. */}
        {[152, 212].map((x) => (
          <rect
            key={x}
            x={x}
            y="66"
            width="36"
            height="20"
            rx="1"
            fill="rgb(var(--court-ink))"
            fillOpacity="0.2"
          />
        ))}
      </g>

      {/* --- The rail across the well, separating the court from the gallery.
              Kept thin and low so it crosses behind counsel, not over them. --- */}
      <g>
        <rect
          x="0"
          y="186"
          width="400"
          height="5"
          fill="rgb(var(--court-gold))"
          fillOpacity="0.55"
        />
        {Array.from({ length: 21 }, (_, i) => (
          <rect
            key={i}
            x={i * 20 + 4}
            y="191"
            width="3"
            height="18"
            fill="rgb(var(--court-gold))"
            fillOpacity="0.22"
          />
        ))}
        <rect
          x="0"
          y="209"
          width="400"
          height="3"
          fill="rgb(var(--court-ink))"
          fillOpacity="0.25"
        />
      </g>

      {/* --- Counsel tables, one either side, angled toward the bench. The
              presenter's centre stays clear: that is where the eye goes. --- */}
      {[
        { d: "M26 170 L128 166 L134 184 L20 188 Z" },
        { d: "M272 166 L374 170 L380 188 L266 184 Z" },
      ].map(({ d }) => (
        <path
          key={d}
          d={d}
          fill="url(#chamber-wood)"
          stroke="rgb(var(--court-gold))"
          strokeOpacity="0.7"
          strokeWidth="1"
        />
      ))}
    </svg>
  );
}
