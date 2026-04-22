import os
import re

from config import client, MODEL
from tools.file_tools import read_file, write_file, safe_join


def _extract_error_paths(build_output: str) -> list[str]:
    if not build_output:
        return []
    # Next.js/Turbopack error lines often look like: ./app/.../file.tsx:3:1
    matches = re.findall(r"\./([^\s:]+\.(?:ts|tsx|js|jsx)):\d+:\d+", build_output)
    # preserve order + dedupe
    seen = set()
    ordered = []
    for path in matches:
        if path not in seen:
            seen.add(path)
            ordered.append(path)
    return ordered


def _choose_fix_target(state, repo_root):
    build_output = state.get("build_output", "")
    for rel_path in _extract_error_paths(build_output):
        try:
            full = safe_join(repo_root, rel_path)
            if os.path.exists(full):
                return rel_path, full
        except Exception:
            continue

    last = state.get("last_modified")
    if not last:
        return None, None

    rel_path = last["path"]
    return rel_path, safe_join(repo_root, rel_path)


def _file_role_rules(rel_path: str) -> str:
    normalized = rel_path.replace("\\", "/")
    if normalized.endswith("/route.ts") or normalized.endswith("/route.tsx"):
        return (
            "- This is a Next.js Route Handler file.\n"
            "- Keep only route handler exports (GET/POST/PATCH/PUT/DELETE/etc).\n"
            "- Do NOT add a default React component export.\n"
            "- Do NOT import React hooks/components in this file.\n"
        )
    return (
        "- Preserve the file's role and public contract.\n"
        "- If this is a page component, keep it as a component file only.\n"
        "- Do NOT embed API route handlers inside page components.\n"
    )

def fixer(state, repo_root):
    rel_path, full_path = _choose_fix_target(state, repo_root)
    if not rel_path or not full_path:
        state["errors"] = ["No last_modified file to fix"]
        return state

    current = read_file(full_path)
    role_rules = _file_role_rules(rel_path)

    prompt = f"""
    You are fixing one Next.js App Router file with minimal corrective edits.

    Build error:
    {state.get("build_output","")}

    File path: {rel_path}

    Current file content:
    {current}

    Goal:
    Fix the code so `npx next build` succeeds, while preserving existing behavior and structure.

    Rules:
    - Make the smallest viable correction for the concrete build error.
    - Preserve existing UI and logic unless directly required by the error.
    - Do NOT simplify/replace the file with placeholder content.
    - Do NOT move responsibilities between files.
    {role_rules}
    - Output ONLY the full corrected file content
    - No markdown fences, no explanations
    """

    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "Return code only. No markdown."},
            {"role": "user", "content": prompt},
        ],
        temperature=0
    )

    fixed = resp.choices[0].message.content or ""
    write_file(full_path, fixed)

    state["diffs"].append({"path": rel_path, "snippet": fixed[:2000]})
    state["errors"] = None
    state["fix_attempts"] = (state.get("fix_attempts") or 0) + 1
    return state
