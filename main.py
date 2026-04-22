import json
import os
import sys
from datetime import datetime

from graph import build_graph
from plans.loader import load_plan
from repo_indexer import detect_project_metadata, generate_repo_map

REPO_ROOT = "../next-app"


def parse_args(raw_args: list[str]) -> tuple[str, bool, str | None]:
    args = list(raw_args)
    is_dry_run = "--dry-run" in args
    if is_dry_run:
        args.remove("--dry-run")

    plan_path = None
    if "--plan" in args:
        idx = args.index("--plan")
        if idx + 1 >= len(args):
            raise ValueError("--plan requires a JSON file path")
        plan_path = args[idx + 1]
        del args[idx : idx + 2]

    task = " ".join(args).strip() or "Create a login page using existing components"
    return task, is_dry_run, plan_path


def main():
    task, is_dry_run, plan_path = parse_args(sys.argv[1:])

    repo_map = generate_repo_map(REPO_ROOT)
    project_metadata = detect_project_metadata(REPO_ROOT)

    structured_plan = None
    if plan_path:
        structured_plan = load_plan(plan_path)
        task = structured_plan.task

    graph = build_graph(REPO_ROOT, plan_mode=bool(structured_plan))

    result = graph.invoke(
        {
            "task": task,
            "repo_map": repo_map,
            "project_metadata": project_metadata,
            "plan": None,
            "structured_plan": structured_plan,
            "current_step": 0,
            "diffs": [],
            "build_output": None,
            "build_exit_code": None,
            "last_cmd_exit_code": None,
            "errors": None,
            "dry_run": is_dry_run,
        }
    )

    log_data = {
        "task": result.get("task"),
        "plan": result.get("plan") or (
            structured_plan.model_dump(mode="json") if structured_plan else None
        ),
        "steps_run": result.get("current_step"),
        "diffs": result.get("diffs"),
        "build_exit_code": result.get("build_exit_code"),
        "build_output": result.get("build_output"),
        "fix_attempts": result.get("fix_attempts", 0),
        "reviewer_decision": "Approved"
        if not result.get("errors")
        else f"Rejected: {result.get('errors')}",
    }

    os.makedirs(".logs", exist_ok=True)
    today_str = datetime.now().strftime("%Y-%m-%d")
    log_path = f".logs/task-{today_str}.json"

    logs = []
    if os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                logs = json.load(f)
        except Exception:
            pass

    if not isinstance(logs, list):
        logs = [logs]

    log_data["timestamp"] = datetime.now().isoformat()
    logs.append(log_data)

    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=2)

    print(f"Workflow finished. Logs saved to {log_path}")


if __name__ == "__main__":
    main()
