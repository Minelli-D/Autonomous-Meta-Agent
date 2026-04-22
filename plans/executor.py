import json
import os
import re
from typing import Any, Dict, Set

from pydantic import BaseModel, ValidationError

from plans.schema import (
    AssertBuildSuccessStep,
    AssertContainsStep,
    CreateFileStep,
    EditFileStep,
    LLMStep,
    Plan,
    PlanConstraints,
    RunCmdStep,
)
from tools.agent_tools import AgentTools


def _is_forbidden(path: str, forbidden: str) -> bool:
    normalized_path = path.replace("\\", "/")
    normalized_forbidden = forbidden.replace("\\", "/")
    return (
        normalized_path == normalized_forbidden
        or normalized_path.startswith(f"{normalized_forbidden}/")
        or normalized_forbidden in normalized_path
    )


def enforce_constraints(constraints: PlanConstraints | None, changed_files: Set[str]) -> None:
    if not constraints:
        return

    if constraints.max_files_changed is not None and len(changed_files) > constraints.max_files_changed:
        raise RuntimeError("Exceeded max_files_changed")

    if constraints.forbid_paths:
        for path in changed_files:
            for forbidden in constraints.forbid_paths:
                if _is_forbidden(path, forbidden):
                    raise RuntimeError(f"Forbidden path touched: {path}")


def _generate_content(prompt: str) -> str:
    from config import MODEL, client

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": "Return only the file content. No markdown fences or explanations.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0,
    )
    return (response.choices[0].message.content or "").strip()


def _generate_patch(prompt: str, path: str, existing: str) -> str:
    from config import MODEL, client

    patch_prompt = f"""
Generate a unified diff patch for exactly one file.
File path: {path}
Current file content:
{existing}

Task:
{prompt}

Rules:
- Return only a valid unified diff.
- The target file must be exactly: {path}
- No markdown fences.
""".strip()

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "Return only unified diff text."},
            {"role": "user", "content": patch_prompt},
        ],
        temperature=0,
    )
    patch = (response.choices[0].message.content or "").strip()

    target = f"+++ b/{path}"
    if target not in patch:
        raise RuntimeError(f"Generated patch targets an unexpected file for {path}")

    return patch


def _generate_full_file_from_edit_prompt(prompt: str, path: str, existing: str) -> str:
    full_prompt = f"""
Rewrite this file to satisfy the task.
File path: {path}

Current content:
{existing}

Task:
{prompt}

Rules:
- Return only the complete file content.
- No markdown fences.
""".strip()
    return _generate_content(full_prompt)


class _LLMCreateDecision(BaseModel):
    action: str
    path: str
    content: str


class _LLMEditDecision(BaseModel):
    action: str
    path: str
    patch_prompt: str


def _resolve_llm_step(
    step: LLMStep, existing_paths: Set[str]
) -> _LLMCreateDecision | _LLMEditDecision:
    from config import MODEL, client

    if not step.allowed_paths:
        raise RuntimeError("llm_step requires at least one allowed path")

    decision_prompt = f"""
Return strict JSON for exactly one operation.

Analysis/context:
{step.analysis}

Allowed actions: {json.dumps(step.allowed_actions)}
Allowed paths: {json.dumps(step.allowed_paths)}
Existing paths among allowed paths: {json.dumps(sorted(existing_paths))}

Rules:
- action must be one of allowed actions.
- path must exactly match one allowed path.
- If action is edit_file, path must be in Existing paths among allowed paths.
- If a target path does not exist yet, prefer create_file.
- For create_file, include: action, path, content.
- For edit_file, include: action, path, patch_prompt.
- Keep changes deterministic and minimal; do not over-engineer.
- Do not introduce new dependencies.
- Do not assume path aliases like @/ unless confirmed in repo context.
- Prefer relative imports when alias configuration is not explicit.
- Prefer plain React + fetch patterns.
- Do not assume UI libraries, styling frameworks, validation libraries, ORM, authentication, database, env vars, file I/O, or external storage unless already present and required.
- If data state is needed and no DB layer exists, use deterministic module-scoped in-memory state.
- Choose the simplest valid implementation when anything is ambiguous.
- No markdown. JSON only.
""".strip()

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "Return strict JSON only."},
            {"role": "user", "content": decision_prompt},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )

    raw = (response.choices[0].message.content or "").strip()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"llm_step returned invalid JSON: {exc}") from exc

    action = payload.get("action")
    path = payload.get("path")
    if action not in step.allowed_actions:
        raise RuntimeError(f"llm_step chose forbidden action: {action}")
    if path not in step.allowed_paths:
        raise RuntimeError(f"llm_step chose forbidden path: {path}")
    if action == "edit_file" and path not in existing_paths:
        raise RuntimeError(f"llm_step chose edit_file for missing path: {path}")

    try:
        if action == "create_file":
            return _LLMCreateDecision.model_validate(payload)
        if action == "edit_file":
            return _LLMEditDecision.model_validate(payload)
    except ValidationError as exc:
        raise RuntimeError(f"llm_step payload failed validation: {exc}") from exc

    raise RuntimeError(f"Unsupported llm_step action: {action}")


def execute_plan(plan: Plan, tools: AgentTools, state: Dict[str, Any]) -> Dict[str, Any]:
    changed_files: Set[str] = set()

    for step in plan.steps:
        if isinstance(step, CreateFileStep):
            if step.content_source:
                content = _generate_content(step.content_source.prompt)
            else:
                content = step.content or ""

            result = tools.write_file(step.path, content)
            if result.startswith("Error:"):
                raise RuntimeError(result)

            changed_files.add(step.path)
            state["diffs"].append({"path": step.path, "snippet": content[:2000]})
            state["last_modified"] = {"path": step.path, "content": content}

        elif isinstance(step, EditFileStep):
            existing = tools.read_file(step.path)
            if existing.startswith("Error:"):
                raise RuntimeError(existing)

            patch = _generate_patch(step.patch_source.prompt, step.path, existing)
            result = tools.apply_patch(step.path, patch)
            if "successfully" not in result.lower():
                rewritten = _generate_full_file_from_edit_prompt(
                    step.patch_source.prompt, step.path, existing
                )
                write_result = tools.write_file(step.path, rewritten)
                if write_result.startswith("Error:"):
                    raise RuntimeError(result)
                changed_files.add(step.path)
                state["diffs"].append({"path": step.path, "snippet": rewritten[:2000]})
                state["last_modified"] = {"path": step.path, "content": rewritten}
                enforce_constraints(plan.constraints, changed_files)
                continue

            updated = tools.read_file(step.path)
            changed_files.add(step.path)
            state["diffs"].append({"path": step.path, "snippet": patch[:2000]})
            state["last_modified"] = {"path": step.path, "content": updated}

        elif isinstance(step, RunCmdStep):
            output = tools.run_cmd(step.cmd)
            state["build_output"] = output
            match = re.search(r"Exit code:\s*(-?\d+)", output)
            state["last_cmd_exit_code"] = int(match.group(1)) if match else None

        elif isinstance(step, AssertContainsStep):
            content = tools.read_file(step.path)
            if content.startswith("Error:"):
                raise RuntimeError(content)
            if step.text not in content:
                rewrite_prompt = (
                    f"Adjust this file so it includes the exact text: {step.text}\n"
                    "Preserve existing behavior and keep it valid for Next.js."
                )
                rewritten = _generate_full_file_from_edit_prompt(
                    rewrite_prompt, step.path, content
                )
                write_result = tools.write_file(step.path, rewritten)
                if write_result.startswith("Error:"):
                    raise AssertionError(f"Text not found in {step.path}")
                changed_files.add(step.path)
                state["diffs"].append({"path": step.path, "snippet": rewritten[:2000]})
                state["last_modified"] = {"path": step.path, "content": rewritten}
                reread = tools.read_file(step.path)
                if reread.startswith("Error:") or step.text not in reread:
                    raise AssertionError(f"Text not found in {step.path}")

        elif isinstance(step, AssertBuildSuccessStep):
            exit_code = state.get("build_exit_code")
            if exit_code is None:
                exit_code = state.get("last_cmd_exit_code")
            if exit_code != 0:
                raise AssertionError(f"Build failed with exit code {exit_code}")

        elif isinstance(step, LLMStep):
            existing_paths: Set[str] = set()
            for allowed_path in step.allowed_paths:
                read_result = tools.read_file(allowed_path)
                if not read_result.startswith("Error:"):
                    existing_paths.add(allowed_path)

            decision = _resolve_llm_step(step, existing_paths)
            if isinstance(decision, _LLMCreateDecision):
                result = tools.write_file(decision.path, decision.content)
                if result.startswith("Error:"):
                    raise RuntimeError(result)
                changed_files.add(decision.path)
                state["diffs"].append({"path": decision.path, "snippet": decision.content[:2000]})
                state["last_modified"] = {"path": decision.path, "content": decision.content}
            else:
                existing = tools.read_file(decision.path)
                if existing.startswith("Error:"):
                    raise RuntimeError(existing)
                patch = _generate_patch(decision.patch_prompt, decision.path, existing)
                result = tools.apply_patch(decision.path, patch)
                if "successfully" not in result.lower():
                    rewritten = _generate_full_file_from_edit_prompt(
                        decision.patch_prompt, decision.path, existing
                    )
                    write_result = tools.write_file(decision.path, rewritten)
                    if write_result.startswith("Error:"):
                        raise RuntimeError(result)
                    changed_files.add(decision.path)
                    state["diffs"].append({"path": decision.path, "snippet": rewritten[:2000]})
                    state["last_modified"] = {"path": decision.path, "content": rewritten}
                    enforce_constraints(plan.constraints, changed_files)
                    continue
                updated = tools.read_file(decision.path)
                changed_files.add(decision.path)
                state["diffs"].append({"path": decision.path, "snippet": patch[:2000]})
                state["last_modified"] = {"path": decision.path, "content": updated}

        enforce_constraints(plan.constraints, changed_files)

    state["current_step"] = len(plan.steps)
    return state


def plan_executor(state: Dict[str, Any], repo_root: str) -> Dict[str, Any]:
    plan = state.get("structured_plan")
    if not isinstance(plan, Plan):
        raise RuntimeError("Missing validated plan in state")

    configured_root = os.path.abspath(repo_root)
    plan_root = os.path.abspath(os.path.join(os.getcwd(), plan.repo_root))
    if plan_root != configured_root:
        raise RuntimeError(
            f"Plan repo_root mismatch. expected={configured_root} plan={plan_root}"
        )

    tools = AgentTools(repo_root, dry_run=state.get("dry_run", False))
    return execute_plan(plan, tools, state)
