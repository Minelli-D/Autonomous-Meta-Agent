import json
import os
import re
from config import client, MODEL
from tools.file_tools import safe_join

def check_policy(state, repo_root):
    policy_errors = []
    
    # Check each modified file
    for diff in state.get("diffs", []):
        path = diff.get("path", "")
        if not path: continue
        
        try:
            if state.get("dry_run"):
                last_mod = state.get("last_modified", {})
                if last_mod.get("path") == path:
                    content = last_mod.get("content", "")
                else:
                    continue # During dry run we can't reliably read unwritten files
            else:
                full_path = safe_join(repo_root, path)
                if not os.path.exists(full_path):
                    continue
                    
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()
                
            # 1. Validate 'use client' correctness with stricter React patterns
            lines = content.splitlines()
            header = "\n".join(lines[:5])
            has_client = ("'use client'" in header) or ('"use client"' in header)
            has_server = ("'use server'" in header) or ('"use server"' in header)

            hook_pattern = re.compile(r"\buse(State|Effect|Context|Ref|Reducer|Callback|Memo)\s*\(")
            event_pattern = re.compile(r"\bon[A-Z][A-Za-z0-9_]*\s*=")
            needs_client = bool(hook_pattern.search(content) or event_pattern.search(content))
            
            if needs_client and not has_client:
                for i, line in enumerate(lines, 1):
                    if hook_pattern.search(line) or event_pattern.search(line):
                        policy_errors.append(f"{path}:{i} - Uses client-side hook/event but missing 'use client' directive at top.")
                        break

            if has_client and has_server:
                policy_errors.append(f"{path}:1 - File cannot contain both 'use client' and 'use server' directives.")

            if has_client and re.search(r"\bexport\s+const\s+metadata\b", content):
                policy_errors.append(f"{path}:1 - Client component should not export Next.js metadata.")
                        
            # 2. Validate imports exist (filesystem) for relative imports
            # Only reliably available for checks if we are NOT in dry_run because we need the base paths intact on disk
            if not state.get("dry_run"):
                import_pattern = re.compile(r"""import\s.*?from\s+['"](\.[^'"]+)['"]""")
                for i, line in enumerate(content.splitlines(), 1):
                    m = import_pattern.search(line)
                    if m:
                        import_path = m.group(1)
                        if not hasattr(locals(), 'full_path') or not full_path:
                            continue
                        base_dir = os.path.dirname(full_path)
                        target_base = os.path.normpath(os.path.join(base_dir, import_path))
                        
                        found = False
                        for ext in ["", ".ts", ".tsx", ".js", ".jsx", ".css"]:
                            if os.path.exists(target_base + ext):
                                found = True
                                break
                        if not found and os.path.isdir(target_base):
                            for ext in ["/index.ts", "/index.tsx", "/index.js"]:
                                if os.path.exists(target_base + ext):
                                    found = True
                                    break
                        if not found:
                            policy_errors.append(f"{path}:{i} - Relative import '{import_path}' does not resolve to an existing local file.")
        except Exception:
            pass
            
    return policy_errors

def reviewer(state, repo_root):
    policy_errors = check_policy(state, repo_root)
    build_failed = state.get("build_exit_code") not in (None, 0)

    # Deterministic fast path: avoid noisy LLM reviews when objective checks pass
    if not policy_errors and not build_failed:
        state["errors"] = None
        return state

    prompt = f"""
You are a strict senior Next.js reviewer.

Task:
{state['task']}

Changes summary:
{json.dumps(state['diffs'], indent=2)}

Build Output:
{state.get('build_output', 'No build executed')}

Static Check / Policy Errors detected programmatically:
{json.dumps(policy_errors, indent=2)}

Review carefully:

- Are imports valid?
- Is Next.js router used correctly?
- Are client/server components correct?
- Are there TypeScript issues implied by build output?
- Is any hallucinated component used?
- Did the build fail?

If build contains errors, approved MUST be false.
If there are Static Check errors, approved MUST be false.

Return ONLY valid JSON:

{{
  "approved": true or false,
  "reason": "actionable reason + file + line hint"
}}
"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "You output strict JSON only."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )

    content = response.choices[0].message.content.strip()

    try:
        review = json.loads(content)
    except json.JSONDecodeError:
        state["errors"] = ["Reviewer returned invalid JSON"]
        return state

    if not review.get("approved", False):
        state["errors"] = [review.get("reason", "Unknown error")]
    else:
        state["errors"] = None

    return state
