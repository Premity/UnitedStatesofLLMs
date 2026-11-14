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
          fillOpacity="0.3"
          stroke="rgb(var(--court-gold))"
          strokeOpacity="0.25"
          strokeWidth="0.75"
        />
      ))}

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

    </svg>
  );
}


/**
 * The furniture that stands between the viewer and the people.
 *
 * Split out of `Chamber` rather than drawn in it, because z-order is the
 * whole point: a bench the judge sits *behind* has to paint over the judge,
 * and one SVG behind every sprite can only ever paint under them. That was
 * the "imposed on top of the bench" problem -- the drawing was correct and
 * the stacking was backwards.
 *
 * Each piece is positioned against the sprite it belongs to rather than in
 * one shared coordinate space, so a sprite moving does not leave its
 * furniture behind.
 */

/**
 * The bench the judge rises from behind.
 *
 * The drawing is the original one -- a wide plinth, a long low front, a lit
 * lip and two recessed panels. Only the stacking changed: it renders in
 * front of the judge instead of behind him. An intermediate version boxed
 * him in with side returns and read as a cage; a bench is a flat face seen
 * from the front, and that is all it needs to be.
 */
export function JudgeBench() {
  return (
    <svg
      aria-hidden
      data-testid="judge-bench"
      // The room's own viewBox and the room's own box on screen. The bench
      // keeps the exact coordinates it had inside `Chamber` -- x 124 to 276,
      // centred on 200 -- so it cannot drift relative to the room.
      //
      // Earlier passes gave this its own viewBox and sized it as a
      // percentage of the judge sprite. That is what broke the centring:
      // `inset-x-0` pins left:0 and a `w-[460%]` then grows rightward, so
      // the bench needed a -180% shift and had -39.5%. Sharing the room's
      // coordinate space removes the arithmetic entirely.
      viewBox="0 0 400 240"
      preserveAspectRatio="none"
      className="pointer-events-none absolute inset-0 z-20 h-full w-full"
    >
      <defs>
        {/* Wood, and opaque -- which is the whole point.

            In `Chamber` the solids are translucent `ink` and that works,
            because everything behind them is the page. This bench is not in
            `Chamber`: it paints over the judge, whose plinth is a dark
            `benchJudge` brown. Translucent `ink` (a light tan under Oak)
            over that brown composites to a washed grey, and because the
            gradient crossed the judge's edge the bench came out two
            different colours with a seam down the figure.

            So the stops are mixed against `--court-bg` here rather than at
            paint time. The result is the same colour the committed bench
            had over the page, and now it is that colour everywhere
            regardless of what it covers. */}
        <linearGradient id="bench-wood" x1="0" y1="0" x2="0" y2="1">
          <stop
            offset="0%"
            stopColor="color-mix(in srgb, rgb(var(--court-ink)) 55%, rgb(var(--court-bg)))"
          />
          <stop
            offset="100%"
            stopColor="color-mix(in srgb, rgb(var(--court-ink)) 80%, rgb(var(--court-bg)))"
          />
        </linearGradient>
      </defs>

      {/* Plinth, wider than the bench and set below it. */}
      <path
        d="M132 92 L268 92 L276 112 L124 112 Z"
        fill="color-mix(in srgb, rgb(var(--court-ink)) 45%, rgb(var(--court-bg)))"
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
        fill="url(#bench-wood)"
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
          fill="color-mix(in srgb, rgb(var(--court-ink)) 88%, rgb(var(--court-bg)))"
        />
      ))}
    </svg>
  );
}

/**
 * The presenter's lectern.
 *
 * One surface, on the side facing the bench, with nothing on the side
 * facing the viewer -- counsel addresses the court across it, so that is
 * the only face that needs to exist.
 *
 * Drawn in the room's own 400x240 coordinates, like the bench and for the
 * same reason: the presenter stands on the room's centre line (x=200), so
 * placing the lectern there needs no arithmetic. Every sprite-relative
 * version of this came out lopsided -- `inset-x-0` pins left:0 while a
 * width override grows rightward, so the shape needed a translate nobody
 * could get right by eye, and one wing always hung off centre.
 *
 * Three earlier versions failed differently and are worth not repeating. A
 * front panel with side returns read as a dock: three sides around a figure
 * is a cage. A wide flat slab read as a table dropped behind them, because
 * stretching a shallow shape flattens the perspective out of it. And a
 * sprite-scoped one would not stay centred.
 */
export function PresenterStand() {
  return (
    <svg
      aria-hidden
      data-testid="presenter-stand"
      viewBox="0 0 400 240"
      preserveAspectRatio="none"
      // Behind the figure. The presenter has to be fully visible -- at
      // z-20 the lectern crossed the face and the role's letter, and no
      // amount of moving it down fixed that, because the problem was the
      // layer and not the height.
      className="pointer-events-none absolute inset-0 z-0 h-full w-full"
    >
      <defs>
        {/* Opaque, for the same reason as the bench: a lectern that changes
            colour depending on whether the floor or a baluster is behind it
            is not a solid object. */}
        <linearGradient id="stand-wood" x1="0" y1="0" x2="0" y2="1">
          <stop
            offset="0%"
            stopColor="color-mix(in srgb, rgb(var(--court-ink)) 55%, rgb(var(--court-bg)))"
          />
          <stop
            offset="100%"
            stopColor="color-mix(in srgb, rgb(var(--court-ink)) 78%, rgb(var(--court-bg)))"
          />
        </linearGradient>
      </defs>

      {/* The face, centred on x=200 and widening toward the viewer.

          Sized against the presenter, not against the room: a lectern is a
          personal stand, so a bit wider than the figure and no more. At
          x=160..240 it was 80 of the room's 400 units -- four times the
          sprite's width, which is a bench, and it swallowed whoever stood
          at it. The judge's bench is six times its figure because a bench
          genuinely is a long desk; a lectern is not.

          Drawn behind the figure, it reads only where it extends past the
          silhouette, so it is a little wider than the sprite rather than
          exactly its width. */}
      <path
        d="M175 176 L225 176 L232 202 L168 202 Z"
        fill="url(#stand-wood)"
        stroke="rgb(var(--court-gold))"
        strokeOpacity="0.7"
        strokeWidth="1"
      />
      {/* The lit top edge, which is what makes it a surface rather than a
          shape painted on the floor. */}
      <rect
        x="173"
        y="172"
        width="54"
        height="5"
        rx="2"
        fill="rgb(var(--court-gold))"
        fillOpacity="0.6"
      />
    </svg>
  );
}

/**
 * The rail that separates the court from the gallery.
 *
 * In front of counsel, not behind them: a barrier the public sits behind is
 * the thing that makes a courtroom read as divided, and one drawn behind
 * the figures is just a line on the wall.
 *
 * It lives here rather than in `Chamber` for that reason alone -- `Chamber`
 * paints under every sprite, so nothing in it can cross in front of one.
 * Room coordinates, like the rest of the furniture.
 */
export function GalleryRail() {
  return (
    <svg
      aria-hidden
      data-testid="gallery-rail"
      viewBox="0 0 400 240"
      preserveAspectRatio="none"
      className="pointer-events-none absolute inset-0 z-20 h-full w-full"
    >
      {/* The top rail. Opaque, so counsel passes behind it cleanly rather
          than showing through the woodwork. */}
      <rect
        x="0"
        y="186"
        width="400"
        height="5"
        fill="color-mix(in srgb, rgb(var(--court-gold)) 55%, rgb(var(--court-bg)))"
      />
      {Array.from({ length: 21 }, (_, i) => (
        <rect
          key={i}
          x={i * 20 + 4}
          y="191"
          width="3"
          height="16"
          fill="color-mix(in srgb, rgb(var(--court-gold)) 30%, rgb(var(--court-bg)))"
        />
      ))}
      <rect
        x="0"
        y="207"
        width="400"
        height="3"
        fill="color-mix(in srgb, rgb(var(--court-ink)) 30%, rgb(var(--court-bg)))"
      />
    </svg>
  );
}
