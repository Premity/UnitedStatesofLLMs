"""Judge quota management and daily rate tracking.

Enforces strict OpenRouter free-tier quota limits:
- Maximum 50 requests/day TOTAL across the free account.
- Hard guardrail: never let the day's total pass 40 requests.
- Judge calls per case:
    - Arm A (raw): 1
    - Arm B (rag): 1
    - Arm C (single_attacker): 2
    - Arm D (full_council): 3
    - Arm E (self_consistency): 1
- Running count maintained in `data/eval/quota_log.json`.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

MAX_DAILY_QUOTA: int = 40
ACCOUNT_DAILY_CEILING: int = 50

JUDGE_CALLS_PER_CASE: dict[str, int] = {
    "raw": 1,
    "rag": 1,
    "single_attacker": 2,
    "full_council": 3,
    "self_consistency": 1,
}


class QuotaExceededError(RuntimeError):
    """Raised when an operation would exceed the daily judge call quota (40 calls)."""


def get_expected_calls(arm_key: str, case_count: int = 1) -> int:
    """Calculate expected judge calls for a given arm and number of cases."""
    calls_per_case = JUDGE_CALLS_PER_CASE.get(arm_key, 1)
    return calls_per_case * case_count


class QuotaTracker:
    """Tracks judge calls and enforces daily safety limits."""

    def __init__(self, log_path: Path | None = None) -> None:
        self.log_path = log_path or Path("data/eval/quota_log.json")

    @staticmethod
    def _today_utc() -> str:
        return datetime.now(UTC).strftime("%Y-%m-%d")

    def load(self) -> dict[str, Any]:
        """Load current quota data from disk."""
        if not self.log_path.exists():
            return {"daily_usage": {}, "total_calls": 0, "history": []}
        try:
            return json.loads(self.log_path.read_text(encoding="utf-8"))
        except Exception:
            return {"daily_usage": {}, "total_calls": 0, "history": []}

    def get_today_usage(self, date_str: str | None = None) -> int:
        """Get the number of judge calls consumed today (or on date_str) in UTC."""
        date_key = date_str or self._today_utc()
        data = self.load()
        daily = data.get("daily_usage", {}).get(date_key, {})
        return int(daily.get("calls", 0))

    def check_quota(
        self,
        expected_calls: int,
        *,
        date_str: str | None = None,
        max_quota: int = MAX_DAILY_QUOTA,
    ) -> tuple[bool, int, int]:
        """Verify that expected_calls will not breach max_quota.

        Returns:
            Tuple of (allowed, current_today_usage, remaining_after_expected).

        Raises:
            QuotaExceededError if today's usage + expected_calls > max_quota.
        """
        today_usage = self.get_today_usage(date_str)
        projected = today_usage + expected_calls
        if projected > max_quota:
            raise QuotaExceededError(
                f"Judge call quota exceeded: {today_usage} calls used today (UTC), "
                f"{expected_calls} expected. Projected total {projected} exceeds "
                f"the daily safety limit of {max_quota} (account ceiling: {ACCOUNT_DAILY_CEILING})."
            )
        remaining = max_quota - projected
        return True, today_usage, remaining

    def record_call(
        self,
        case_id: str,
        arm_key: str,
        calls: int = 1,
        *,
        backend: str = "api",
        notes: str = "",
    ) -> int:
        """Record judge call(s) in the quota log and return new today total."""
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        data = self.load()
        today = self._today_utc()

        daily_usage = data.setdefault("daily_usage", {})
        today_entry = daily_usage.setdefault(
            today, {"calls": 0, "limit": MAX_DAILY_QUOTA, "ceiling": ACCOUNT_DAILY_CEILING}
        )
        if calls > 0:
            today_entry["calls"] = int(today_entry.get("calls", 0)) + calls
            data["total_calls"] = int(data.get("total_calls", 0)) + calls

        history = data.setdefault("history", [])
        history.append(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "case_id": case_id,
                "arm": arm_key,
                "calls": calls,
                "backend": backend,
                "notes": notes,
            }
        )

        self.log_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return int(today_entry["calls"])
