"""Downsize the source emblem into the favicon set.

    uv run python scripts/build_favicons.py

Reads `runtime/frontend/src/img/favicon.png` and writes the icons
`runtime/frontend/index.html` links to. The source is a 1280x1095 RGBA
emblem, which is too large to ship as a favicon; this just scales it down.

Transparency is kept, so the icon sits on whatever the browser puts behind
it. Two things are not plain scaling:

**The squaring.** The source is wider than it is tall, and resizing it to a
square canvas would stretch the scales out of true, so it is centred on a
transparent square instead.

**The white strokes are dropped.** The source traces every laurel leaf and
the edges of the scales in *opaque white*, about 6% of the image. At 1280px
those are invisible hairlines. Shrunk to 16px they are a large fraction of
each shape, and the resampler blends them into the surrounding blue -- which
renders as a pale halo around the emblem and reads as "the transparency is
broken" on dark browser chrome. It is not: the file is transparent, and the
white is in the art. Clearing it to alpha 0 is what makes the small sizes
look like the emblem rather than a smudge.

**The blue is lifted.** A favicon sits on chrome the page does not control
and cannot query -- the same file is drawn on a near-black tab bar and on a
white one. The source navy is 10.2:1 against white and 1.4:1 against a dark
tab, so on half the browsers in use the emblem is a dark shape on a dark
field. `ICON_BLUE` is the colour with the best *worst* case across both:
3.57:1 everywhere, over the 3:1 WCAG asks of a graphical object. Chosen by
measuring rather than by eye -- see the ratios in the commit that added it.

This is the one place the icon deliberately departs from the source art, and
it only affects the favicon; nothing else in the app uses this file.

The outputs are committed, so this runs only when the source art changes.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runtime/frontend/src/img/favicon.png"
PUBLIC = ROOT / "runtime/frontend/public"

#: What the emblem's navy becomes in the icon. The source is rgb(16, 65, 121),
#: which disappears into dark browser chrome (1.4:1 against a dark tab bar).
#: This clears 3:1 on every common chrome, light and dark.
ICON_BLUE = (64, 134, 180)

SIZES = {
    "favicon-16.png": 16,
    "favicon-32.png": 32,
    "favicon-180.png": 180,
}


def drop_white_strokes(art: Image.Image) -> Image.Image:
    """Clear the source's opaque white outlines to full transparency.

    They are hairlines at full size and a halo at 16px. `min(r, g, b)` rather
    than a per-channel test so off-white antialiasing goes with them; the
    emblem's own blue is nowhere near this threshold, so nothing of the
    artwork is touched.
    """
    out = art.copy()
    pixels = out.load()
    width, height = out.size

    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if a and min(r, g, b) > 200:
                pixels[x, y] = (r, g, b, 0)

    return out.crop(out.getbbox())


def recolour(art: Image.Image) -> Image.Image:
    """Lift the emblem's blue to `ICON_BLUE`, keeping the alpha shape.

    A flat replacement rather than a hue shift: the art is one colour plus
    antialiasing, so mapping every visible pixel to the target and leaving
    alpha alone preserves the edges exactly while changing what they are.
    """
    out = art.copy()
    pixels = out.load()
    width, height = out.size

    for y in range(height):
        for x in range(width):
            alpha = pixels[x, y][3]
            if alpha:
                pixels[x, y] = (*ICON_BLUE, alpha)

    return out


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(f"Source art not found: {SOURCE}")

    art = Image.open(SOURCE).convert("RGBA")
    art = art.crop(art.getbbox())  # drop the source's own whitespace margin
    art = drop_white_strokes(art)
    art = recolour(art)

    PUBLIC.mkdir(parents=True, exist_ok=True)

    for name, size in SIZES.items():
        scaled = art.copy()
        scaled.thumbnail((size, size), Image.LANCZOS)

        # Square canvas, transparent. Scaled to fit rather than stretched to
        # fill: a picture of scales must not lean.
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        canvas.alpha_composite(scaled, ((size - scaled.width) // 2, (size - scaled.height) // 2))

        out = PUBLIC / name
        canvas.save(out, optimize=True)
        print(f"{out.relative_to(ROOT)}  {size}x{size}  {out.stat().st_size:,}B")


if __name__ == "__main__":
    main()
