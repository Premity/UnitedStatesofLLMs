"""Downsize the source emblem into the favicon set.

    uv run python scripts/build_favicons.py

Reads `runtime/frontend/src/img/favicon.png` and writes the icons
`runtime/frontend/index.html` links to. The source is a 1280x1095 RGBA
emblem, which is too large to ship as a favicon; this just scales it down.

Transparency is kept, so the icon sits on whatever the browser puts behind
it. The one thing not done by plain scaling is the squaring: the source is
wider than it is tall, and resizing it to a square canvas would stretch the
scales out of true, so it is centred on a transparent square instead.

The outputs are committed, so this runs only when the source art changes.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runtime/frontend/src/img/favicon.png"
PUBLIC = ROOT / "runtime/frontend/public"

SIZES = {
    "favicon-16.png": 16,
    "favicon-32.png": 32,
    "favicon-180.png": 180,
}


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(f"Source art not found: {SOURCE}")

    art = Image.open(SOURCE).convert("RGBA")
    art = art.crop(art.getbbox())  # drop the source's own whitespace margin

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
