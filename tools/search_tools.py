import json
from config import client, MODEL
import os
def find_similar_files(repo_root, keyword):
    matches = []
    for root, dirs, files in os.walk(repo_root):
        for file in files:
            if keyword.lower() in file.lower():
                matches.append(os.path.join(root, file))
    return matches[:5]

    prompt = f"""
    You are a senior Next.js architect.

    Repo structure:
    {state['repo_map']}

    Task:
    {state['task']}

    Break into atomic file-level steps.
    Return JSON array like:
    [
    {{
        "action": "create_file",
        "path": "app/login/page.tsx",
        "description": "Create login page"
    }}
    ]
    """

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )

    plan = json.loads(response.choices[0].message.content)

    state["plan"] = plan
    state["current_step"] = 0
    return state