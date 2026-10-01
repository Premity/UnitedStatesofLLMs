"""Minimal SVG primitives shared by the figure generators.

Keeps one visual language across every figure: same type scale, same palette,
same arrowheads. Diagrams are authored in absolute coordinates — these helpers
only remove the repetitive markup, they do not lay anything out.
"""

FONT = "Calibri, Carlito, 'Segoe UI', sans-serif"
MONO = "Consolas, 'DejaVu Sans Mono', monospace"

# Muted, print-safe. Distinguishable in greyscale by lightness, not hue alone.
INK = "#1a1a1a"
MUTED = "#6b6b6b"
LINE = "#9a9a9a"

FILLS = {
    "external": "#eef2f7",
    "local": "#e8f0e8",
    "core": "#f4eee6",
    "offline": "#f0eef4",
    "plain": "#ffffff",
    "accent": "#e4ecf4",
}
STROKES = {
    "external": "#5b7fa6",
    "local": "#5f8560",
    "core": "#a3835a",
    "offline": "#7b6f99",
    "plain": "#9a9a9a",
    "accent": "#5b7fa6",
}


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def header(w: int, h: int) -> str:
    """Open the SVG and declare the arrowhead markers."""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}"
     viewBox="0 0 {w} {h}" font-family="{FONT}">
<defs>
  <marker id="a" viewBox="0 0 10 10" refX="9" refY="5"
          markerWidth="7" markerHeight="7" orient="auto-start-reverse">
    <path d="M 0 0 L 10 5 L 0 10 z" fill="{LINE}"/>
  </marker>
  <marker id="ad" viewBox="0 0 10 10" refX="9" refY="5"
          markerWidth="7" markerHeight="7" orient="auto-start-reverse">
    <path d="M 0 0 L 10 5 L 0 10 z" fill="{INK}"/>
  </marker>
</defs>
<rect width="{w}" height="{h}" fill="#ffffff"/>
"""


def footer() -> str:
    return "</svg>\n"


def box(x, y, w, h, label, kind="plain", sub=None, rx=4, fs=13, bold=True):
    """A labelled rounded rectangle. `sub` lines render smaller, beneath."""
    f, s = FILLS[kind], STROKES[kind]
    out = (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
        f'fill="{f}" stroke="{s}" stroke-width="1.2"/>\n'
    )
    lines = [label] if isinstance(label, str) else list(label)
    subs = [] if sub is None else ([sub] if isinstance(sub, str) else list(sub))
    total = len(lines) * (fs + 3) + len(subs) * 13
    cy = y + h / 2 - total / 2 + fs
    for ln in lines:
        out += (
            f'<text x="{x + w / 2}" y="{cy}" text-anchor="middle" font-size="{fs}" '
            f'fill="{INK}"{' font-weight="600"' if bold else ""}>{esc(ln)}</text>\n'
        )
        cy += fs + 3
    for sb in subs:
        out += (
            f'<text x="{x + w / 2}" y="{cy}" text-anchor="middle" font-size="11" '
            f'fill="{MUTED}">{esc(sb)}</text>\n'
        )
        cy += 13
    return out


def band(x, y, w, h, title, kind="plain", dash=False):
    """A grouping container with its title set in the top-left."""
    f, s = FILLS[kind], STROKES[kind]
    d = ' stroke-dasharray="5 3"' if dash else ""
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{f}" '
        f'fill-opacity="0.45" stroke="{s}" stroke-width="1.2"{d}/>\n'
        f'<text x="{x + 12}" y="{y + 18}" font-size="11.5" font-weight="700" '
        f'fill="{STROKES[kind]}" letter-spacing="0.8">{esc(title)}</text>\n'
    )


def arrow(x1, y1, x2, y2, label=None, dark=False, dash=False, lx=None, ly=None, anchor="middle"):
    m = "ad" if dark else "a"
    c = INK if dark else LINE
    d = ' stroke-dasharray="5 3"' if dash else ""
    out = (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{c}" '
        f'stroke-width="1.4" marker-end="url(#{m})"{d}/>\n'
    )
    if label:
        tx = lx if lx is not None else (x1 + x2) / 2
        ty = ly if ly is not None else (y1 + y2) / 2 - 6
        out += (
            f'<text x="{tx}" y="{ty}" text-anchor="{anchor}" font-size="10.5" '
            f'fill="{MUTED}">{esc(label)}</text>\n'
        )
    return out


def poly(points, label=None, dark=False, dash=False, lx=0, ly=0, anchor="middle"):
    """An elbowed connector through a list of (x, y) points."""
    m = "ad" if dark else "a"
    c = INK if dark else LINE
    d = ' stroke-dasharray="5 3"' if dash else ""
    pts = " ".join(f"{x},{y}" for x, y in points)
    out = (
        f'<polyline points="{pts}" fill="none" stroke="{c}" stroke-width="1.4" '
        f'marker-end="url(#{m})"{d}/>\n'
    )
    if label:
        out += (
            f'<text x="{lx}" y="{ly}" text-anchor="{anchor}" font-size="10.5" '
            f'fill="{MUTED}">{esc(label)}</text>\n'
        )
    return out


def text(x, y, s, fs=12, fill=None, weight=None, anchor="start", mono=False, style=None):
    w = f' font-weight="{weight}"' if weight else ""
    fam = f' font-family="{MONO}"' if mono else ""
    st = f' font-style="{style}"' if style else ""
    return (
        f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-size="{fs}" '
        f'fill="{fill or INK}"{w}{fam}{st}>{esc(s)}</text>\n'
    )


def diamond(cx, cy, w, h, label, kind="accent", fs=12):
    f, s = FILLS[kind], STROKES[kind]
    pts = f"{cx},{cy - h / 2} {cx + w / 2},{cy} {cx},{cy + h / 2} {cx - w / 2},{cy}"
    out = f'<polygon points="{pts}" fill="{f}" stroke="{s}" stroke-width="1.2"/>\n'
    lines = [label] if isinstance(label, str) else list(label)
    ty = cy - (len(lines) - 1) * (fs + 2) / 2 + fs / 2 - 1
    for ln in lines:
        out += (
            f'<text x="{cx}" y="{ty}" text-anchor="middle" font-size="{fs}" '
            f'fill="{INK}" font-weight="600">{esc(ln)}</text>\n'
        )
        ty += fs + 2
    return out


def stadium(x, y, w, h, label, kind="plain", fs=13):
    return box(x, y, w, h, label, kind=kind, rx=h / 2, fs=fs)


def caption(x, y, s):
    return text(x, y, s, fs=11, fill=MUTED, style="italic")


def write(path, parts):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("".join(parts))
    print(f"wrote {path}")


def region(x, y, w, h, title, kind="plain", gap=4):
    """A double-ruled container, the SVG equivalent of a box-drawing ╔══╗ frame.

    Used for deployment regions that are genuinely separate — a different
    compose file, a different lifecycle — as opposed to `band`, which groups
    components that merely belong together.
    """
    s = STROKES[kind]
    f = FILLS[kind]
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="7" fill="{f}" '
        f'fill-opacity="0.30" stroke="{s}" stroke-width="1.4"/>\n'
        f'<rect x="{x + gap}" y="{y + gap}" width="{w - 2 * gap}" height="{h - 2 * gap}" '
        f'rx="4" fill="none" stroke="{s}" stroke-width="0.9" stroke-opacity="0.65"/>\n'
        f'<rect x="{x + 18}" y="{y - 9}" width="{len(title) * 6.15 + 20}" height="19" rx="3" '
        f'fill="#ffffff" stroke="{s}" stroke-width="1"/>\n'
        f'<text x="{x + 29}" y="{y + 4}" font-size="11.5" font-weight="700" '
        f'fill="{s}" letter-spacing="0.7">{esc(title)}</text>\n'
    )


def unit(x, y, w, h, name, meta, lines, kind="local", fs=13):
    """A deployable unit: bold name, a dim meta string on the same line
    (port, image), then bulleted internals."""
    f, s = FILLS[kind], STROKES[kind]
    out = (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="4" fill="{f}" '
        f'stroke="{s}" stroke-width="1.3"/>\n'
        f'<text x="{x + 14}" y="{y + 22}" font-size="{fs}" font-weight="700" '
        f'fill="{INK}">{esc(name)}</text>\n'
    )
    if meta:
        out += (
            f'<text x="{x + w - 14}" y="{y + 22}" font-size="10.5" fill="{MUTED}" '
            f'text-anchor="end" font-family="{MONO}">{esc(meta)}</text>\n'
        )
    ty = y + 40
    for ln in lines:
        out += (
            f'<text x="{x + 14}" y="{ty}" font-size="11" fill="{MUTED}">'
            f'<tspan fill="{LINE}">•</tspan>  {esc(ln)}</text>\n'
        )
        ty += 15
    return out
