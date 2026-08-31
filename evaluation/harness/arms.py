"""The ablation arms.

The abstract claims the council beats a single pass. That claim is only
meaningful against a ladder that isolates *what* is doing the work: retrieval,
adversarial challenge, or having two challengers rather than one.

Each arm differs from the one above it in exactly one respect.
"""

from __future__ import annotations

from dataclasses import dataclass

from council_core.models.debate import Role


@dataclass(frozen=True)
class Arm:
    """One configuration under test."""

    key: str
    label: str
    description: str
    retrieval_enabled: bool
    attackers: tuple[Role, ...]
    max_rounds: int

    @property
    def is_single_pass(self) -> bool:
        """No attackers means no debate — the presenter answers alone."""
        return len(self.attackers) == 0


ARMS: dict[str, Arm] = {
    "raw": Arm(
        key="raw",
        label="A — Single pass, no retrieval",
        description=(
            "The presenter answers from parametric knowledge alone. Establishes "
            "the fabrication and overconfidence baseline the project is arguing against."
        ),
        retrieval_enabled=False,
        attackers=(),
        max_rounds=1,
    ),
    "rag": Arm(
        key="rag",
        label="B — Single pass with retrieval",
        description=(
            "Retrieval-grounded, but no adversarial challenge. Isolates how much "
            "grounding alone contributes, so the council is not credited for it."
        ),
        retrieval_enabled=True,
        attackers=(),
        max_rounds=1,
    ),
    "single_attacker": Arm(
        key="single_attacker",
        label="C — One attacker",
        description=(
            "Presenter, doctrinal attacker, judge. Isolates the value of adversarial "
            "challenge as such, before asking whether a second attacker adds anything."
        ),
        retrieval_enabled=True,
        attackers=(Role.ATTACKER_DOCTRINAL,),
        max_rounds=2,
    ),
    "full_council": Arm(
        key="full_council",
        label="D — Full council",
        description=(
            "Both attackers, separated by mandate. The proposed system. Its gain over "
            "arm C is the specific claim that splitting doctrinal from evidentiary "
            "challenge is worth the second model."
        ),
        retrieval_enabled=True,
        attackers=(Role.ATTACKER_DOCTRINAL, Role.ATTACKER_EVIDENTIARY),
        max_rounds=3,
    ),
}
