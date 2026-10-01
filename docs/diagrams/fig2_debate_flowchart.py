"""Figure 2 — Debate workflow flowchart.

One request, start to finish. Two swimlanes: the offline pipeline that must
have completed before any debate runs, and the per-request flow through the
graph. Decision diamonds carry the two termination conditions, which together
guarantee the debate halts.
"""

import os

from _svgkit import arrow, band, box, caption, diamond, footer, header, poly, stadium, text, write

W, H = 1180, 1080
p = [header(W, H)]

p.append(text(W / 2, 34, "Figure 2 — Debate Workflow", fs=17, weight="700", anchor="middle"))
p.append(
    text(
        W / 2,
        53,
        "From question to dissent log, with termination guarantees",
        fs=12,
        fill="#6b6b6b",
        anchor="middle",
    )
)

# ── Offline prerequisite lane ─────────────────────────────────────────────
p.append(
    band(
        40,
        74,
        1100,
        98,
        "PREREQUISITE  ·  offline, run once per corpus version",
        kind="offline",
        dash=True,
    )
)
p.append(stadium(66, 100, 130, 50, "Start", kind="offline", fs=12))
p.append(box(226, 100, 150, 50, "Read manifests", kind="offline", fs=12, sub="scope is fixed"))
p.append(
    box(
        406,
        100,
        170,
        50,
        "Fetch documents",
        kind="offline",
        fs=12,
        sub="treaties · cases · resolutions",
    )
)
p.append(
    box(
        606,
        100,
        200,
        50,
        "Chunk at citation granularity",
        kind="offline",
        fs=11.5,
        sub="article · paragraph",
    )
)
p.append(
    box(836, 100, 190, 50, "Embed + upsert", kind="offline", fs=12, sub="Qdrant + citation index")
)
for x1, x2 in [(196, 224), (376, 404), (576, 604), (806, 834)]:
    p.append(arrow(x1, 125, x2, 125))

# ── Request flow ──────────────────────────────────────────────────────────
CX = 360  # main column centre

p.append(stadium(CX - 85, 196, 170, 46, "Question + facts", kind="accent", fs=12.5))
p.append(arrow(CX, 242, CX, 268))

p.append(
    box(
        CX - 110,
        268,
        220,
        52,
        "Retrieve context",
        kind="local",
        fs=12.5,
        sub="top-k passages from Qdrant",
    )
)
p.append(arrow(CX, 320, CX, 346))

p.append(
    box(
        CX - 110,
        346,
        220,
        52,
        "Presenter builds case",
        kind="local",
        fs=12.5,
        sub="discrete, contestable arguments",
    )
)
p.append(arrow(CX, 398, CX, 424))

# fan-out
p.append(text(CX, 418, "", fs=10))
p.append(
    box(
        CX - 240,
        424,
        205,
        56,
        "Doctrinal attacker",
        kind="local",
        fs=12.5,
        sub=["legal characterisation:", "tests, elements, interpretation"],
    )
)
p.append(
    box(
        CX + 35,
        424,
        205,
        56,
        "Evidentiary attacker",
        kind="local",
        fs=12.5,
        sub=["factual predicate:", "sufficiency, mens rea, attribution"],
    )
)
p.append(poly([(CX, 424), (CX, 410), (CX - 137, 410), (CX - 137, 422)]))
p.append(poly([(CX, 424), (CX, 410), (CX + 137, 410), (CX + 137, 422)]))
p.append(text(CX + 252, 452, "run concurrently", fs=10.5, fill="#6b6b6b"))
p.append(text(CX + 252, 466, "independent mandates", fs=10.5, fill="#6b6b6b"))

# fan-in
p.append(poly([(CX - 137, 480), (CX - 137, 498), (CX, 498), (CX, 516)]))
p.append(poly([(CX + 137, 480), (CX + 137, 498), (CX, 498)]))

p.append(
    box(
        CX - 125,
        516,
        250,
        52,
        "Resolve every citation",
        kind="core",
        fs=12.5,
        sub="against the corpus index",
    )
)

# citation status fan-out to the right
p.append(poly([(CX + 125, 542), (700, 542)]))
p.append(box(700, 500, 420, 86, "", kind="plain"))
p.append(
    text(
        716,
        522,
        "Citation status — attached to the claim, not reported later",
        fs=11.5,
        weight="700",
    )
)
for i, (code, desc) in enumerate(
    [
        ("resolved", "locator found, quote matches"),
        ("misquoted", "locator found, quote diverges"),
        ("unresolved", "no such locator → fabrication signal"),
        ("out_of_corpus", "real authority, not indexed"),
    ]
):
    yy = 540 + i * 13
    p.append(text(716, yy, f"{code}", fs=10.5, mono=True, weight="700"))
    p.append(text(812, yy, f"— {desc}", fs=10.5, fill="#6b6b6b"))

p.append(arrow(CX, 568, CX, 594))

p.append(
    box(
        CX - 125,
        594,
        250,
        56,
        "Judge rules",
        kind="local",
        fs=12.5,
        sub=["sustains or overrules each objection,", "with a stated reason"],
    )
)
p.append(arrow(CX, 650, CX, 678))

# ── Decisions ─────────────────────────────────────────────────────────────
p.append(diamond(CX, 716, 250, 76, ["Novel objections", "raised this round?"]))
p.append(arrow(CX + 125, 716, 700, 716, "no"))
p.append(poly([(CX, 754), (CX, 788)], label="yes", lx=CX + 16, ly=775, anchor="start"))

p.append(diamond(CX, 826, 250, 76, ["round < max_rounds?"], kind="accent"))
p.append(arrow(CX + 125, 826, 700, 826, "no  ·  hard ceiling"))

# loop back to presenter
p.append(
    poly(
        [(CX - 125, 826), (62, 826), (62, 372), (CX - 112, 372)],
        label="yes — next round",
        lx=74,
        ly=356,
        anchor="start",
        dark=True,
    )
)
p.append(text(74, 700, "presenter rebuts", fs=10.5, fill="#6b6b6b"))

# ── Terminal ──────────────────────────────────────────────────────────────
p.append(
    box(
        700,
        688,
        420,
        56,
        "Emit verdict",
        kind="accent",
        fs=12.5,
        sub=["conclusion · calibrated confidence · reasoning"],
    )
)
p.append(
    box(
        700,
        790,
        420,
        56,
        "Publish dissent log",
        kind="core",
        fs=12.5,
        sub=["every overruled objection + the judge's reason"],
    )
)
p.append(arrow(910, 744, 910, 788))

p.append(
    box(
        700,
        876,
        420,
        50,
        "Persist run artifact",
        kind="local",
        fs=12.5,
        sub="prompts, model ids, seeds, citations — written even on failure",
    )
)
p.append(arrow(910, 846, 910, 874))

p.append(stadium(825, 956, 170, 46, "End", kind="plain", fs=12.5))
p.append(arrow(910, 926, 910, 954))

p.append(
    caption(
        40,
        1004,
        "The debate halts on whichever condition fires first. The round ceiling is "
        "absolute: it applies in fixed and auto modes alike, so no configuration "
        "can produce an unbounded loop.",
    )
)
p.append(
    caption(
        40,
        1022,
        "Citations are resolved before the judge reads an argument, so a fabricated "
        "authority cannot influence the ruling — the gap this design closes.",
    )
)
p.append(caption(40, 1040, "The dissent log, not the conclusion, is the primary output."))

p.append(footer())
write(os.path.join(os.path.dirname(__file__), "fig2-debate-flowchart.svg"), p)
