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


@dataclass(frozen=True)
class SelfConsistencyArm(Arm):
    """Arm E: Compute-matched self-consistency control (ADR 0011).

    Samples the presenter alone with retrieval multiple times at temperature 0.7,
    aggregates via majority voting with agreement rate as confidence, and passes
    the aggregate to the judge once.

    The sample count `samples` (n) is derived per case from Arm D's actual call
    count on the same case, ensuring total model calls match Arm D within ±1.
    """

    samples: int | None = None
    temperature: float = 0.7

    def with_samples(self, n: int) -> SelfConsistencyArm:
        """Return a copy of this arm configured with n samples."""
        return SelfConsistencyArm(
            key=self.key,
            label=self.label,
            description=self.description,
            retrieval_enabled=self.retrieval_enabled,
            attackers=self.attackers,
            max_rounds=self.max_rounds,
            samples=n,
            temperature=self.temperature,
        )

    def for_case(self, d_calls: int, *, has_judge: bool = True) -> SelfConsistencyArm:
        """Derive sample count from Arm D's call count on the same case."""
        from harness.sampling import derive_sample_count

        return self.with_samples(derive_sample_count(d_calls, has_judge=has_judge))


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
        # Same ceiling as C, so C and D differ only in the second attacker, and
        # the app's default (`DebateConfig.max_rounds`), so the evaluation
        # scores what the app runs. The app allows a third round; it is untested.
        max_rounds=2,
    ),
    "self_consistency": SelfConsistencyArm(
        key="self_consistency",
        label="E — Self-consistency control (compute-matched)",
        description=(
            "Presenter sampled n times with retrieval (temperature 0.7), majority-vote "
            "aggregated, then evaluated once by the judge. Matches Arm D's total model calls "
            "on each case to isolate multi-agent debate from pure compute scaling."
        ),
        retrieval_enabled=True,
        attackers=(),
        max_rounds=1,
        samples=None,
        temperature=0.7,
    ),
}
