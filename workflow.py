"""Offline, checkpointed dry run of a guarded refactor planner."""

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from guardrails import validate_plan

RESERVED_TOKENS = 32
ALLOWED_PATHS = frozenset({"src/parser.py", "tests/test_parser.py"})
FIXTURE_RESPONSES = (
    '{"summary":',
    '{"summary":"Separate token parsing from validation.","paths":["src/parser.py","tests/test_parser.py"]}',
)


@dataclass
class Run:
    budget: int
    attempts: int = 0
    status: str = "running"
    last_error: str | None = None
    plan: dict | None = None


def save(path: Path, run: Run) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode="w", dir=path.parent, encoding="utf-8", delete=False) as tmp:
        temporary = Path(tmp.name)
        try:
            json.dump(asdict(run), tmp, indent=2)
            tmp.close()
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def execute(run: Run, path: Path, pause_after_primary: bool) -> None:
    while run.status == "running":
        if run.attempts >= len(FIXTURE_RESPONSES) or (run.attempts + 1) * RESERVED_TOKENS > run.budget:
            run.status = "blocked"
            run.last_error = "attempt limit or token reservation cap reached"
            save(path, run)
            return

        raw = FIXTURE_RESPONSES[run.attempts]
        run.attempts += 1
        save(path, run)  # Reserve the attempt before using its output.
        try:
            run.plan = validate_plan(raw, ALLOWED_PATHS)
        except ValueError as error:
            run.last_error = str(error)
            save(path, run)
            if pause_after_primary and run.attempts == 1:
                return
        else:
            run.status = "complete"
            save(path, run)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=Path(".runs/refactor.json"))
    parser.add_argument("--budget", type=int)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--pause-after-primary", action="store_true")
    args = parser.parse_args()
    if args.resume:
        if args.budget is not None or not args.checkpoint.is_file():
            parser.error("resume requires an existing checkpoint and its original budget")
        run = Run(**json.loads(args.checkpoint.read_text(encoding="utf-8")))
        if run.status == "complete":
            run.plan = validate_plan(json.dumps(run.plan), ALLOWED_PATHS)
    else:
        if args.checkpoint.exists():
            parser.error("checkpoint already exists, use --resume or choose a new path")
        if args.budget is not None and args.budget < 0:
            parser.error("budget must be non-negative")
        run = Run(budget=args.budget if args.budget is not None else 64)

    execute(run, args.checkpoint, args.pause_after_primary)
    print(json.dumps({**asdict(run), "reserved_tokens": run.attempts * RESERVED_TOKENS}, indent=2))
    return int(run.status == "blocked")


if __name__ == "__main__":
    raise SystemExit(main())
