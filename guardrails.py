"""Independent checks before a generated plan can leave the workflow."""

import json


def validate_plan(raw: str, allowed_paths: frozenset[str]) -> dict:
    plan = json.loads(raw)
    if not isinstance(plan, dict) or set(plan) != {"summary", "paths"}:
        raise ValueError("expected a plan with summary and paths")
    summary = plan["summary"]
    if not isinstance(summary, str) or not 1 <= len(summary.strip()) <= 300:
        raise ValueError("summary must contain 1 to 300 characters")
    paths = plan["paths"]
    if not isinstance(paths, list) or not 1 <= len(paths) <= 3:
        raise ValueError("expected one to three paths")
    if any(not isinstance(path, str) or path not in allowed_paths for path in paths):
        raise ValueError("plan includes a path outside the allowlist")
    return {"summary": summary.strip(), "paths": paths}
