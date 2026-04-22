import argparse
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AGENT_ROOT = os.path.dirname(SCRIPT_DIR)
if AGENT_ROOT not in sys.path:
    sys.path.insert(0, AGENT_ROOT)

from plans.executor import execute_plan
from plans.loader import load_plan
from tools.agent_tools import AgentTools


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test the strict plan executor")
    parser.add_argument(
        "--plan",
        default="plans/examples/sample_plan.json",
        help="Path to a plan JSON file (default: plans/examples/sample_plan.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Run without writing files (default: true)",
    )
    args = parser.parse_args()

    plan = load_plan(args.plan)

    repo_root = plan.repo_root
    if not os.path.isabs(repo_root):
        repo_root = os.path.abspath(os.path.join(os.getcwd(), repo_root))

    tools = AgentTools(repo_root, dry_run=args.dry_run)
    state = {
        "task": plan.task,
        "diffs": [],
        "dry_run": args.dry_run,
        "build_exit_code": 0,
        "last_cmd_exit_code": None,
        "current_step": 0,
    }

    result = execute_plan(plan, tools, state)

    if result.get("current_step") != len(plan.steps):
        print("Smoke test failed: not all steps executed", file=sys.stderr)
        return 1

    summary = {
        "task": result.get("task"),
        "steps_executed": result.get("current_step"),
        "diffs": result.get("diffs"),
    }
    print("Smoke test passed")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
