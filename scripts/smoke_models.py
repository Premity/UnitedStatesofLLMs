"""Ping every role's configured model once. Development aid."""

import asyncio

from council_core.llm import CouncilLLM, RoleModels

ROLES = ("presenter", "attacker_doctrinal", "attacker_evidentiary", "judge")


async def main() -> None:
    models = RoleModels()
    for role in ROLES:
        config = models.for_role(role)
        try:
            resp = await CouncilLLM(config, role="smoke-test").complete(
                system="You are a test harness.", user="Reply with exactly: ok"
            )
            print(f"OK   {role:22} {config.model_id:40} -> {resp.content.strip()[:40]!r}")
        except Exception as exc:
            print(f"FAIL {role:22} {config.model_id:40} -> {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
