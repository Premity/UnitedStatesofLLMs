"""The four council roles.

Each role owns its prompt ids, its response schema, and how it turns a model
response into domain objects. Roles are modules, not services: the debate is
sequential, so four containers would buy network hops and nothing else. See
`docs/adr/0003-single-orchestrator-service.md`.
"""

from app.roles.attacker import AttackerRole
from app.roles.judge import JudgeRole
from app.roles.presenter import PresenterRole

__all__ = ["AttackerRole", "JudgeRole", "PresenterRole"]
