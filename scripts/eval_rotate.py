"""Run the extended case tier across several Groq and OpenRouter keys.

Keys are used until they run out, not rationed: the script keeps one Groq key
and one OpenRouter key until a provider refuses for quota, then swaps only that
key and resumes. The harness runs with `--resume`, so a case that stopped on
its third arm restarts at the third arm; finished arms are never re-run.

A key counts as out of quota when:
- Groq or OpenRouter returns a rate-limit error after the gateway's own
  retries. The harness is stopped at once, so the arms after the failed one
  don't fail too, and the key rests for the wait Groq's error names (24 hours
  if it names none; OpenRouter's until 00:05 UTC);
- the harness's own judge cap (40 attempts per OpenRouter account per UTC day)
  has no room for the arms still pending. Each OpenRouter key has its own
  quota log in `data/eval-quota/`; the `.env` key keeps `data/eval/quota_log.json`
  so what it spent earlier still counts.

Keys live in `.keys/groq.txt` and `.keys/openrouter.txt`, one per line,
gitignored. Keys from the same account share its limit, so list one per
account. A key is never printed, logged or written to the state file: it is
named by a hash prefix (`groq-1a2b3c4d`), and any harness output line that
contains a key is redacted before it is shown or logged.

    uv run python scripts/eval_rotate.py --status    # keys, rests, pending cases
    uv run python scripts/eval_rotate.py             # run until done or every key rests
    uv run python scripts/eval_rotate.py --wait      # ...and sleep until a key is back
    uv run python scripts/eval_rotate.py --max-cases 3
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "evaluation"))

from harness.cases import EXTENDED_CASE_IDS  # noqa: E402
from harness.quota import JUDGE_CALLS_PER_CASE, MAX_DAILY_QUOTA, QuotaTracker  # noqa: E402

KEYS_DIR = ROOT / ".keys"
STATE_PATH = KEYS_DIR / "state.json"
EVAL_DIR = ROOT / "data" / "eval"
DEFAULT_QUOTA_LOG = EVAL_DIR / "quota_log.json"
QUOTA_DIR = ROOT / "data" / "eval-quota"  # not under data/eval: */*.json there is a result
LOG_DIR = ROOT / "data" / "logs"

ARMS = ("raw", "rag", "single_attacker", "full_council", "self_consistency")
ATTEMPTS_PER_JUDGE_CALL = 3  # what the harness reserves per expected call
MAX_TRIES_PER_CASE = 3  # failures that are not quota: give up on the case after this many
GROQ_DEFAULT_REST = timedelta(hours=24)


def now() -> datetime:
    return datetime.now(UTC)


def label(prefix: str, key: str) -> str:
    return f"{prefix}-{hashlib.sha256(key.encode()).hexdigest()[:8]}"


def read_keys(path: Path) -> list[str]:
    if not path.exists():
        return []
    keys: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and line not in keys:
            keys.append(line)
    return keys


def env_file_value(name: str) -> str | None:
    env = ROOT / ".env"
    if not env.exists():
        return None
    for line in env.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith(f"{name}="):
            return line.split("=", 1)[1].strip().strip("'\"") or None
    return None


# ── State: which key is in use, and which keys are resting ────────────────────


def load_state() -> dict:
    state = json.loads(STATE_PATH.read_text(encoding="utf-8")) if STATE_PATH.exists() else {}
    state.setdefault("resting_until", {})
    return state


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    STATE_PATH.chmod(0o600)


def resting_until(state: dict, name: str) -> datetime | None:
    until = state["resting_until"].get(name)
    if until and datetime.fromisoformat(until) > now():
        return datetime.fromisoformat(until)
    return None


def rest(state: dict, name: str, until: datetime) -> None:
    state["resting_until"][name] = until.isoformat()


def next_utc_midnight() -> datetime:
    return (now() + timedelta(days=1)).replace(hour=0, minute=5, second=0, microsecond=0)


def groq_wait(text: str) -> timedelta | None:
    """The wait Groq's rate-limit error names: 'Please try again in 1h2m3.5s'."""
    match = re.search(r"try again in ((?:\d+h)?(?:\d+m)?(?:[\d.]+s)?)", text)
    if not match or not match.group(1):
        return None
    parts = {unit: value for value, unit in re.findall(r"([\d.]+)([hms])", match.group(1))}
    return timedelta(
        hours=float(parts.get("h", 0)),
        minutes=float(parts.get("m", 0)),
        seconds=float(parts.get("s", 0)) + 60,  # a minute's margin
    )


# ── Quota ──────────────────────────────────────────────────────────────────────


def quota_log_for(key: str, name: str) -> Path:
    if key == env_file_value("OPENROUTER_API_KEY"):
        return DEFAULT_QUOTA_LOG
    return QUOTA_DIR / f"{name}.json"


def judge_used(key: str, name: str) -> int:
    return QuotaTracker(quota_log_for(key, name)).get_today_usage()


def reservation(case_id: str) -> int:
    """Judge attempts the harness will reserve for this case's unfinished arms."""
    status = case_status(case_id)
    return sum(
        JUDGE_CALLS_PER_CASE[arm] * ATTEMPTS_PER_JUDGE_CALL
        for arm, s in status.items()
        if s != "completed"
    )


# ── Cases ──────────────────────────────────────────────────────────────────────


def case_status(case_id: str) -> dict[str, str]:
    """Each arm's state on disk: missing, error or completed."""
    status = {}
    for arm in ARMS:
        path = EVAL_DIR / arm / f"{case_id}.json"
        if not path.exists():
            status[arm] = "missing"
            continue
        try:
            status[arm] = json.loads(path.read_text(encoding="utf-8")).get("status", "error")
        except ValueError:
            status[arm] = "error"
    return status


def pending_cases() -> list[str]:
    return [
        case_id
        for case_id in EXTENDED_CASE_IDS
        if any(s != "completed" for s in case_status(case_id).values())
    ]


def is_rate_limit(text: str) -> bool:
    """A key that has run out, as opposed to one request that can never fit.

    Groq raises "Request too large ... tokens per minute" as a RateLimitError when a
    single request exceeds the per-minute cap. Every key has the same cap, so resting
    the key fixes nothing; it is an ordinary failure that spends one of the case's tries.
    """
    lowered = text.lower()
    if "request too large" in lowered:
        return False
    return any(s in lowered for s in ("ratelimit", "rate limit", "rate_limit", "429"))


# ── Choosing keys ──────────────────────────────────────────────────────────────


def pick(keys: dict[str, str], state: dict, taken: set[str], current: str | None, usable):
    """The worker's key if it still works, else the first free one that does.

    `taken` holds the keys other workers hold: two workers on one key would
    drain one account twice as fast and trip its limit mid-case.
    """
    order = sorted(keys, key=lambda k: keys[k] != current)  # current first, file order after
    for key in order:
        name = keys[key]
        if name in taken and name != current:
            continue
        if not resting_until(state, name) and usable(key, name):
            return key
    return None


# ── Running ────────────────────────────────────────────────────────────────────


def run_case(case_id, groq_key, or_key, or_name, secrets, log, prefix) -> tuple[int, str]:
    """Run the harness on one case. Stops it at the first rate-limit error.

    Returns the exit code and the rate-limit error line ('' if none).
    """
    env = {**os.environ, "GROQ_API_KEY": groq_key, "OPENROUTER_API_KEY": or_key}
    env.pop("LITELLM_DEV_ENV_HOT_RELOAD", None)  # would let .env override these keys
    QUOTA_DIR.mkdir(parents=True, exist_ok=True)
    cmd = [
        "uv", "run", "python", "-m", "harness.run",
        "--all-arms", "--tier", "extended", "--case", case_id,
        "--resume", "--go", "--quota-log", str(quota_log_for(or_key, or_name)),
    ]  # fmt: skip
    proc = subprocess.Popen(
        cmd, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    assert proc.stdout is not None
    limit_line = ""
    for line in proc.stdout:
        for secret, name in secrets.items():
            line = line.replace(secret, f"<{name}>")
        log(prefix + line)
        stripped = line.strip()
        if stripped.startswith(("->", "Running arm", "Judge attempts", "Stopping")):
            say(f"{prefix}    {stripped[:300]}")
        if stripped.startswith("-> ERROR") and is_rate_limit(stripped):
            limit_line = stripped
            proc.terminate()  # the arms after this one would fail on the same key
            break
    try:
        code = proc.wait(timeout=60)
    except subprocess.TimeoutExpired:
        proc.kill()
        code = proc.wait()
    return code, limit_line


_print_lock = threading.Lock()


def say(text: str) -> None:
    with _print_lock:
        print(text, flush=True)


def print_status(groq: dict, openrouter: dict, state: dict) -> None:
    def note(name: str) -> str:
        until = resting_until(state, name)
        return f", resting until {until:%Y-%m-%d %H:%M} UTC" if until else ""

    print(f"Groq keys ({len(groq)}):")
    for name in groq.values():
        print(f"  {name}{note(name)}")
    print(f"OpenRouter keys ({len(openrouter)}), judge cap {MAX_DAILY_QUOTA} per UTC day:")
    for key, name in openrouter.items():
        log = quota_log_for(key, name).relative_to(ROOT)
        print(f"  {name}: {judge_used(key, name)}/{MAX_DAILY_QUOTA} used ({log}){note(name)}")
    pending = pending_cases()
    print(f"Pending extended cases ({len(pending)}):")
    for case_id in pending:
        status = case_status(case_id)
        todo = [arm for arm, s in status.items() if s != "completed"]
        detail = "all arms" if len(todo) == len(ARMS) else "from " + ", ".join(todo)
        print(f"  {case_id} ({detail})")


class Runner:
    """Workers share one lock over which cases and keys are taken, and the state file."""

    def __init__(self, groq: dict, openrouter: dict, args: argparse.Namespace) -> None:
        self.groq, self.openrouter, self.args = groq, openrouter, args
        self.secrets = {**groq, **openrouter}
        self.state = load_state()
        self.lock = threading.Lock()
        self.cases_taken: set[str] = set()
        self.keys_taken: set[str] = set()
        self.tries: dict[str, int] = {}
        self.finished = 0
        self.running = 0
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.log_path = LOG_DIR / f"eval-rotate-{now():%Y%m%d}.log"
        self.log_file = self.log_path.open("a", encoding="utf-8")

    def log(self, text: str) -> None:
        with self.lock:
            self.log_file.write(text)
            self.log_file.flush()

    def claim(self, current: dict[str, str | None]):
        """Under the lock: a case and a key pair for one worker, or why there is none.

        Returns (case_id, groq_key, or_key), ("done", wake_time) or ("wait", wake_time).
        """
        if self.args.max_cases is not None and self.finished + self.running >= self.args.max_cases:
            return ("done", None)
        pending = [
            c
            for c in pending_cases()
            if c not in self.cases_taken and self.tries.get(c, 0) < MAX_TRIES_PER_CASE
        ]
        if not pending:
            return ("done", None)
        case_id = pending[0]
        needed = reservation(case_id)
        groq_key = pick(self.groq, self.state, self.keys_taken, current["groq"], lambda k, n: True)
        or_key = pick(
            self.openrouter,
            self.state,
            self.keys_taken,
            current["openrouter"],
            lambda k, n: judge_used(k, n) + needed <= MAX_DAILY_QUOTA,
        )
        if groq_key is None or or_key is None:
            if self.running:  # another worker holds keys; they come back when it finishes
                return ("wait", now() + timedelta(minutes=2))
            if not self.args.wait:
                return ("done", None)
            rests = [t for n in self.secrets.values() if (t := resting_until(self.state, n))]
            return ("wait", min(rests + ([next_utc_midnight()] if or_key is None else [])))
        self.cases_taken.add(case_id)
        self.keys_taken |= {self.groq[groq_key], self.openrouter[or_key]}
        self.running += 1
        return (case_id, groq_key, or_key)

    def worker(self, number: int) -> None:
        prefix = f"[w{number}] " if self.args.workers > 1 else ""
        current: dict[str, str | None] = {"groq": None, "openrouter": None}
        announced_wait = False
        while True:
            with self.lock:
                claim = self.claim(current)
            if claim[0] == "done":
                return
            if claim[0] == "wait":
                wake = claim[1]
                if not announced_wait or self.running == 0:
                    say(f"{prefix}No free keys; waiting until {wake:%Y-%m-%d %H:%M} UTC.")
                    announced_wait = True
                time.sleep(max(60.0, (wake - now()).total_seconds()))
                continue
            announced_wait = False
            case_id, groq_key, or_key = claim
            g_name, o_name = self.groq[groq_key], self.openrouter[or_key]
            current.update(groq=g_name, openrouter=o_name)
            todo = [arm for arm, s in case_status(case_id).items() if s != "completed"]
            say(
                f"{prefix}=== {case_id} [{', '.join(todo)}] on {g_name} + {o_name} "
                f"({now():%Y-%m-%dT%H:%M:%SZ})"
            )
            self.log(f"{prefix}=== {case_id} on {g_name} + {o_name} {now().isoformat()}\n")
            code, limit_line = run_case(
                case_id, groq_key, or_key, o_name, self.secrets, self.log, prefix
            )
            self.log(f"{prefix}=== exit {code} {now().isoformat()}\n")

            with self.lock:
                self.running -= 1
                self.cases_taken.discard(case_id)
                self.keys_taken -= {g_name, o_name}
                if limit_line:
                    # Quota, not a fault: rest the key and resume the case; no try is spent.
                    if "openrouter" in limit_line.lower():
                        rest(self.state, o_name, next_utc_midnight())
                        current["openrouter"] = None
                        say(f"{prefix}    {o_name} is out of quota; resting it until 00:05 UTC.")
                    else:
                        until = now() + (groq_wait(limit_line) or GROQ_DEFAULT_REST)
                        rest(self.state, g_name, until)
                        current["groq"] = None
                        say(
                            f"{prefix}    {g_name} is out of quota; resting it until {until:%Y-%m-%d %H:%M} UTC."
                        )
                    save_state(self.state)
                elif case_id not in pending_cases():
                    self.finished += 1
                else:
                    self.tries[case_id] = self.tries.get(case_id, 0) + 1
                    say(
                        f"{prefix}    exit {code}, case incomplete "
                        f"(try {self.tries[case_id]}/{MAX_TRIES_PER_CASE}); "
                        f"see {self.log_path.relative_to(ROOT)}."
                    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--status", action="store_true", help="Show keys and cases, then exit.")
    parser.add_argument("--max-cases", type=int, default=None, help="Stop after this many cases.")
    parser.add_argument(
        "--wait", action="store_true", help="When every key rests, sleep until one is back."
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Cases to run at once (default 1). Each worker holds its own Groq and OpenRouter "
        "key and loads its own embedding model, about 1.5 GB of RAM.",
    )
    args = parser.parse_args()

    KEYS_DIR.mkdir(mode=0o700, exist_ok=True)
    groq = {k: label("groq", k) for k in read_keys(KEYS_DIR / "groq.txt")}
    openrouter = {k: label("or", k) for k in read_keys(KEYS_DIR / "openrouter.txt")}

    if args.status:
        print_status(groq, openrouter, load_state())
        return 0
    if not groq or not openrouter:
        print("No keys: add them to .keys/groq.txt and .keys/openrouter.txt.", file=sys.stderr)
        return 1
    if args.workers < 1:
        parser.error("--workers must be at least 1")
    workers = min(args.workers, len(groq), len(openrouter))
    if workers < args.workers:
        print(f"Only {workers} worker(s): each needs its own Groq and OpenRouter key.")
    args.workers = workers

    runner = Runner(groq, openrouter, args)
    threads = [threading.Thread(target=runner.worker, args=(n + 1,)) for n in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    runner.log_file.close()
    print(f"Finished {runner.finished} case(s). Log: {runner.log_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
