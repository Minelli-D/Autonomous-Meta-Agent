import json
from config import client, MODEL

def planner(state):
    prompt = f"""
You are a strict senior Next.js architect.
You are a planning compiler, not a designer.

Project metadata:
{json.dumps(state.get("project_metadata", {}), indent=2)}

Repo structure:
{state['repo_map']}

Task:
{state['task']}

Rules:
- Use router_base from metadata when creating pages/routes.
- If has_tailwind=true use Tailwind classes.
- If is_typescript=true prefer .tsx.
- Prefer editing existing files over creating new ones.
- One step = one file.
- Do not introduce new dependencies.
- Do not assume path aliases like @/ unless explicitly confirmed by repo_map/project metadata.
- Prefer relative imports when alias configuration is not confirmed.
- Prefer plain React and fetch for UI/data flow.
- Do not assume UI component libraries or styling frameworks unless clearly detected in repo_map.
- Do not add external validation libraries.
- Do not add ORM, authentication, database, environment variables, or external storage.
- If a backend/data layer is needed and no database exists, use deterministic module-scoped in-memory state.
- Avoid file I/O for app state.
- Keep each step atomic and deterministic; avoid over-engineering.
- For each step description, specify concrete contract details: exact route path (if any), component/export names, API endpoint path, HTTP method, query params, and response shape.
- If any requirement is ambiguous, choose the simplest implementation possible.
- Do not create unexpected files; only create files directly required by the task.

Return ONLY valid JSON:
{{
  "plan": [
    {{
      "action": "create_file" | "edit_file",
      "path": "relative/path.tsx",
      "description": "atomic change"
    }}
  ]
}}
"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "Return strict JSON only."},
            {"role": "user", "content": prompt},
        ],
        temperature=0,
        response_format={"type": "json_object"}
    )

    parsed = json.loads(response.choices[0].message.content)
    state["plan"] = parsed["plan"]
    state["current_step"] = 0
    return state
