"""Generate the favicon set from the source emblem.

    uv run python scripts/build_favicons.py

Reads `runtime/frontend/src/img/favicon.png` and writes the three icons
`runtime/frontend/index.html` links to. The source is a 1280x1095 RGBA
emblem -- scales inside a laurel wreath -- which is neither square nor small
enough to ship as-is.

Two decisions are baked in here rather than left to the browser:

**Two crops, not one scaled image.** The laurel ring collapses into a smudge
at 16px and takes the scales' contrast with it, so the small icon is the
scales alone. The full emblem appears from 32px up, where the ring reads.

**Flattened onto Oak's `--court-bg`.** A favicon cannot follow the theme the
way the drawn courtroom does, and dark-blue art on transparency disappears
against dark browser chrome. A light ground keeps it legible either way.

The outputs are committed, so this runs only when the source art changes.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runtime/frontend/src/img/favicon.png"
PUBLIC = ROOT / "runtime/frontend/public"

#: `--court-bg` under Oak, the default palette (see src/styles/index.css).
OAK_BG = (237, 224, 204, 255)


def square_icon(art: Image.Image, size: int, margin: float, out: Path) -> None:
    """Fit `art` into a square canvas, scaled rather than stretched.

    The emblem is wider than it is tall, so stretching it to a square makes
    the scales lean -- which is the one thing a picture of scales must not do.
    """
    pad = max(1, round(size * margin))
    scaled = art.copy()
    scaled.thumbnail((size - 2 * pad, size - 2 * pad), Image.LANCZOS)

    canvas = Image.new("RGBA", (size, size), OAK_BG)
    canvas.alpha_composite(scaled, ((size - scaled.width) // 2, (size - scaled.height) // 2))
    canvas.convert("RGB").save(out, optimize=True)
    print(f"{out.relative_to(ROOT)}  {size}x{size}  {out.stat().st_size:,}B")


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(f"Source art not found: {SOURCE}")

    source = Image.open(SOURCE).convert("RGBA")

    # Trim to the art's own bounds first, so the margins below are ours to
    # set rather than whatever whitespace the source happened to carry.
    full = source.crop(source.getbbox())
    width, height = full.size

    scales = full.crop(
        (round(width * 0.22), round(height * 0.02), round(width * 0.78), round(height * 0.66))
    )
    scales = scales.crop(scales.getbbox())

    PUBLIC.mkdir(parents=True, exist_ok=True)
    square_icon(scales, 16, 0.06, PUBLIC / "favicon-16.png")
    square_icon(full, 32, 0.06, PUBLIC / "favicon-32.png")
    square_icon(full, 180, 0.08, PUBLIC / "apple-touch-icon.png")


if __name__ == "__main__":
    main()
