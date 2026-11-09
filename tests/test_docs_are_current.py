"""Checks that the docs still describe the repository they are in.

`CLAUDE.md` called the corpus fetcher and indexer "SCAFFOLD ONLY" for two
weeks after both were built, tested and run. Reading that file first, work was
proposed to build what already existed. A checklist in the PR template is easy
to tick without looking; these assertions are not.

Scoped deliberately. They check claims that can be verified mechanically
against the tree -- a path that moved, a count that drifted, a subsystem
described as absent while its code is importable. Prose is left alone, since a
test that guesses at meaning fails for the wrong reasons and gets deleted.

Each failure names the file to edit and what to say.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

DOCS = [
    ROOT / "CLAUDE.md",
    ROOT / "ISSUES.md",
    ROOT / "README.md",
    *sorted((ROOT / "docs").rglob("*.md")),
]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("subsystem", "module"),
    [
        ("corpus fetcher", "pipeline/fetcher/fetcher/main.py"),
        ("ICRC client", "pipeline/fetcher/fetcher/sources/icrc.py"),
        ("corpus indexer", "pipeline/indexer/indexer/main.py"),
    ],
)
def test_a_subsystem_that_exists_is_not_described_as_a_stub(subsystem: str, module: str) -> None:
    """The exact failure this file exists for.

    A module with real code in it must not be called a scaffold or a stub.
    Someone reading that will either rebuild it or reason about the system as
    though retrieval returns nothing.
    """
    source = ROOT / module
    assert source.exists(), f"{module} moved; update this test and the docs that name it"

    # A scaffold is a few lines of imports. Real code is not.
    assert len(source.read_text(encoding="utf-8").splitlines()) > 50

    stale = re.compile(r"SCAFFOLD ONLY|is (?:still )?a stub|are (?:still )?stubs", re.I)
    for doc in DOCS:
        for number, line in enumerate(read(doc).splitlines(), 1):
            if stale.search(line) and subsystem.split()[-1] in line.lower():
                pytest.fail(
                    f"{doc.relative_to(ROOT)}:{number} calls the {subsystem} a stub, "
                    f"but {module} is implemented.\n"
                    f"  {line.strip()}\n"
                    "Describe what it does, or what is actually missing."
                )


#: Roots a documented path may be written relative to. Docs name
#: `app/roles/` inside a paragraph about `runtime/api/`, and that is clearer
#: in prose than the full path would be.
#: Docs that record what the tree *used* to look like. `corpus-findings.md`
#: names `pipeline/fetcher/app/` because that is what the package was called
#: when the bug it describes happened; "fixing" the path would make the
#: write-up wrong.
HISTORICAL_DOCS = {"corpus-findings.md"}

PATH_ROOTS = [
    "",
    "runtime/api",
    "runtime/api/app",
    "runtime/api/app/graph",
    "packages/council-core/src",
    "prompts",
    "runtime/frontend",
    "runtime/frontend/src",
    "packages/council-core/src/council_core",
    "pipeline/fetcher",
    "pipeline/indexer",
    "evaluation",
    "docs",
    "corpus",
]


def test_every_documented_repo_path_exists() -> None:
    """A path that moved is worse than no path: it sends someone nowhere.

    `ISSUES.md` pointed at `app/sources/` long after the package was renamed
    to `fetcher/sources/`.

    A path is accepted if it resolves under any of `PATH_ROOTS`, because docs
    legitimately write one relative to the component under discussion. What
    this catches is a path that resolves nowhere at all.

    Files a doc says are *missing* are the point of those docs, so a path on a
    line that calls it absent is skipped.
    """
    # `docs/planning/` describes work to be done, so it names files that do
    # not exist yet by design. Checking them there would mean deleting this
    # test the first time someone wrote a plan.
    descriptive = [d for d in DOCS if "planning" not in d.parts and d.name not in HISTORICAL_DOCS]

    pattern = re.compile(r"`((?:[\w.-]+/)+[\w.-]*(?:\.py|\.ts|\.tsx|\.md|\.json|\.yml|\.sh|/))`")
    planned = re.compile(
        r"not started|not yet|missing|needed|to be written|does not exist|"
        r"no `?run\.py|would |stretch|future|planned|TODO|— the |-- the ",
        re.I,
    )
    missing: list[str] = []

    for doc in descriptive:
        for number, line in enumerate(read(doc).splitlines(), 1):
            if planned.search(line):
                continue
            for candidate in pattern.findall(line):
                if candidate.startswith(("http", "data/", "/")):
                    continue
                if any(ch in candidate for ch in "*{<"):
                    continue
                if any((ROOT / root / candidate).exists() for root in PATH_ROOTS):
                    continue
                missing.append(f"{doc.relative_to(ROOT)}:{number}  {candidate}")

    assert not missing, (
        "Documented paths that resolve nowhere:\n  "
        + "\n  ".join(missing)
        + "\nFix the path, or say on that line that the file does not exist yet."
    )


def test_quoted_python_test_counts_are_not_wildly_stale() -> None:
    """A count is a claim, and a wrong one makes the paragraph around it suspect.

    Python only. Counted from `def test_` in the files rather than by running
    pytest, which would recurse. Parametrised cases expand at collection time,
    so the static count is a floor -- this fails on a drift big enough to be
    staleness, not on arithmetic.

    The frontend is deliberately not checked here: `it.each` tables expand to
    far more cases than there are `it(` calls, and a static count would be
    wrong in the other direction. Vitest's own total is the only honest source
    for that number, and running it from pytest is not worth the coupling.
    """
    groups = (
        "tests",
        "runtime/api/tests",
        "packages/council-core/tests",
        "pipeline/indexer/tests",
        "pipeline/fetcher/tests",
    )
    actual = sum(
        len(re.findall(r"^\s*(?:async )?def test_", read(path), re.M))
        for group in groups
        for path in (ROOT / group).rglob("test_*.py")
    )

    # Both phrasings the docs actually use: "159 Python tests" and the
    # "(311 tests: 159 Python, 152 frontend)" summary form.
    claimed = re.compile(r"(\d+)\s+Python(?:\s+tests?)?\b", re.I)
    for doc in DOCS:
        for number, line in enumerate(read(doc).splitlines(), 1):
            for match in claimed.finditer(line):
                stated = int(match.group(1))
                assert abs(stated - actual) <= max(15, actual // 4), (
                    f"{doc.relative_to(ROOT)}:{number} says {match.group(0)!r}, "
                    f"but about {actual} Python tests exist.\n  {line.strip()}"
                )


def test_issues_index_table_matches_its_entries() -> None:
    """The table at the top of ISSUES.md lists what is open below it.

    It is the first thing read and the easiest thing to leave behind, so a row
    naming a section that is now resolved is actively misleading.
    """
    text = read(ROOT / "ISSUES.md")

    resolved = {
        heading.strip().lower()
        for heading in re.findall(r"^###\s+\[(?:RESOLVED|DONE)\]\s+(.+)$", text, re.M)
    }

    table = re.findall(r"^\|\s*([^|]+?)\s*\|\s*[^|]+?\s*\|$", text, re.M)
    rows = {row.strip().lower() for row in table} - {"item below", "---"}

    stale = {row for row in rows if row in resolved}
    assert not stale, (
        "ISSUES.md's index table lists items whose sections are resolved: "
        f"{sorted(stale)}.\nRemove the rows, or reopen the entries."
    )


def test_the_pr_template_requires_a_docs_pass() -> None:
    """The process guard itself, so it cannot be quietly dropped."""
    template = read(ROOT / ".github/pull_request_template.md")

    assert "## Docs" in template
    for required in ("ISSUES.md", "CLAUDE.md"):
        assert required in template, (
            f"The PR template no longer asks whether {required} was updated. "
            "That checklist is why these tests have something to check against."
        )


def test_claude_md_commands_exist_in_the_makefile() -> None:
    """CLAUDE.md's command list is the first thing anyone runs.

    `make corpus` was documented as "not yet implemented" while the target
    worked, which is the same class of error in the other direction.
    """
    targets = set(re.findall(r"^([a-z][\w-]*):", read(ROOT / "Makefile"), re.M))

    documented = set(re.findall(r"^make ([a-z][\w-]*)", read(ROOT / "CLAUDE.md"), re.M))

    missing = documented - targets
    assert not missing, f"CLAUDE.md documents make targets that do not exist: {sorted(missing)}"


def test_pytest_collects_this_directory() -> None:
    """These checks are worthless if CI never runs them."""
    config = tomllib.loads(read(ROOT / "pyproject.toml"))
    paths = config["tool"]["pytest"]["ini_options"]["testpaths"]

    assert "tests" in paths, (
        "Root-level `tests/` is not in pytest's testpaths, so the docs checks do not run in CI."
    )


def test_reference_artwork_stays_out_of_a_public_repository() -> None:
    """`runtime/frontend/src/img/` holds art that is not ours to publish.

    `courtroom.png` is the Ace Attorney courtroom, (c) Capcom, kept locally
    while the room was being drawn. This repository is public, so committing
    it would be infringement -- see "Courtroom background art" in ISSUES.md.

    The favicon source is deliberately exempt: it is the project's emblem, and
    `scripts/build_favicons.py` cannot run without it. That exemption is what
    makes this test necessary, because the rule is now a glob plus a negation
    rather than a blanket directory ignore.
    """
    import subprocess

    tracked = subprocess.run(
        ["git", "ls-files", "runtime/frontend/src/img/"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=True,
    ).stdout.split()

    allowed = {"runtime/frontend/src/img/favicon.png"}
    unexpected = set(tracked) - allowed

    assert not unexpected, (
        "Reference artwork is tracked in a public repository:\n  "
        + "\n  ".join(sorted(unexpected))
        + "\nOnly the project's own favicon source belongs here."
    )
