"""Model access. One client, every backend.

See `docs/adr/0002-litellm-model-gateway.md`.
"""

from council_core.llm.client import CouncilLLM, ModelResponse
from council_core.llm.config import ModelConfig, RoleModels

__all__ = ["CouncilLLM", "ModelConfig", "ModelResponse", "RoleModels"]
