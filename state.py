from typing import TypedDict, List, Optional, Dict, Any


class PlanStep(TypedDict, total=False):
    action: str
    path: str
    description: str


class AgentState(TypedDict, total=False):
    task: str
    repo_map: str
    project_metadata: Dict[str, Any]
    plan: Optional[List[PlanStep]]
    structured_plan: Any
    current_step: Optional[int]
    diffs: List[Any]
    build_output: Optional[str]
    errors: Optional[List[str]]
    last_modified: Optional[Dict[str, str]]
    build_exit_code: Optional[int]
    last_cmd_exit_code: Optional[int]
    fix_attempts: Optional[int]
    dry_run: Optional[bool]
