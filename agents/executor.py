from config import client, MODEL
from tools.file_tools import read_file, write_file
from tools.context_builder import build_context
from tools.file_tools import safe_join
import os
import json

def executor(state, repo_root):

    step = state["plan"][state["current_step"]]
    raw_path = step['path']
    
    # Resolve path using router base
    base = (state.get("project_metadata") or {}).get("router_base")
    if base and not raw_path.startswith(base + "/"):
        if not raw_path.startswith(("app/", "pages/", "src/app/", "src/pages/")):
            path = f"{base}/{raw_path}"
        else:
            path = raw_path
    else:
        path = raw_path

    reference_context = build_context(state, repo_root, step)
    
    from tools.agent_tools import AgentTools

    tools_api = AgentTools(repo_root, dry_run=state.get("dry_run", False))

    tools_schema = [
        {
            "type": "function",
            "function": {
                "name": "list_dir",
                "description": "List contents of a directory. Path should be relative to the repo root.",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read the contents of a file. Path should be relative to the repo root.",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "Rewrite the contents of a file completely. Path should be relative to the repo root.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"}
                    },
                    "required": ["path", "content"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "apply_patch",
                "description": "Apply a unified diff patch to a file. Path should be relative to the repo root. Preferred over `write_file` for performance/safety.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "unified_diff": {"type": "string"}
                    },
                    "required": ["path", "unified_diff"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "search_text",
                "description": "Search for query text across relevant files in the repository. Returns matching file paths.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "max_results": {"type": "integer"}
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "run_cmd",
                "description": "Run shell command against repo root. Highly restricted (e.g. `npx next build`, `npx eslint`).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cmd": {"type": "string"}
                    },
                    "required": ["cmd"]
                }
            }
        }
    ]

    prompt = f"""
    You are an autonomous Next.js modifier agent resolving a planned step.
    
    Target primary modification file planned: {path}
    Context task description for this step: {step['description']}
    
    <reference_context>
    {reference_context}
    </reference_context>
    
    Using your tools, complete the requested task.
    You may explore directories, read existing source code, formulate precise patches using `apply_patch` (highly preferred), or overwrite contents entirely using `write_file`.
    Strict constraints:
    - Modify exactly one file for this step: {path}
    - `write_file` and `apply_patch` are allowed only on: {path}
    - Prefer minimal edits and deterministic behavior.
    - Follow React/Next.js safety rules:
      - Add 'use client' only when client hooks/events are used.
      - Do not use client hooks in server components.
      - Avoid introducing new UI libraries or dependencies.
      - Prefer relative imports unless alias config is explicitly known.
    When you are finished modifying the file for this step, output the exact phrase: `DONE` to conclude this iteration loop.
    DO NOT output `DONE` until the modification has actually been completely successfully executed via an explicit tool call parameter payload!
    
    Max iteration limit is 8 tool calls. Use them wisely.
    """

    messages = [
        {"role": "system", "content": "You are a ReAct tool-calling autonomous frontend engineer. Use appropriate tools to modify the codebase safely and concisely. Explicitly output the string `DONE` when the step successfully resolves."},
        {"role": "user", "content": prompt}
    ]

    max_calls = 8
    calls_made = 0
    
    new_diff_log = None
    last_mod_content = None
    did_modify_target = False

    while calls_made < max_calls:
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=tools_schema,
            temperature=0
        )
        
        message = response.choices[0].message
        messages.append(message)
        
        if getattr(message, "content", None) and "DONE" in message.content:
            break
            
        if message.tool_calls:
            for tool_call in message.tool_calls:
                calls_made += 1
                func_name = tool_call.function.name
                
                try:
                    func_args = json.loads(tool_call.function.arguments)
                except Exception as e:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": func_name,
                        "content": f"Failed to parse function arguments context: {e}"
                    })
                    continue
                
                # Execute tool sandbox
                tool_output = ""
                try:
                    if func_name == "list_dir":
                        tool_output = tools_api.list_dir(func_args["path"])
                    elif func_name == "read_file":
                        tool_output = tools_api.read_file(func_args["path"])
                    elif func_name == "write_file":
                        if func_args["path"] != path:
                            tool_output = (
                                f"Error: write_file is restricted to planned path '{path}', "
                                f"got '{func_args['path']}'."
                            )
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "name": func_name,
                                "content": tool_output
                            })
                            continue
                        tool_output = tools_api.write_file(func_args["path"], func_args["content"])
                        new_diff_log = f"Rewritten full file: {func_args['path']}"
                        last_mod_content = func_args["content"]
                        path = func_args['path']  # Update memory tracker of path modified
                        if not tool_output.startswith("Error:"):
                            did_modify_target = True
                    elif func_name == "apply_patch":
                        if func_args["path"] != path:
                            tool_output = (
                                f"Error: apply_patch is restricted to planned path '{path}', "
                                f"got '{func_args['path']}'."
                            )
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "name": func_name,
                                "content": tool_output
                            })
                            continue
                        tool_output = tools_api.apply_patch(func_args["path"], func_args["unified_diff"])
                        new_diff_log = func_args["unified_diff"]
                        path = func_args['path']
                        # Fetch the live view into last_mod_content
                        if "successfully" in tool_output.lower():
                            last_mod_content = tools_api.read_file(func_args["path"])
                            did_modify_target = True
                    elif func_name == "search_text":
                        tool_output = tools_api.search_text(func_args["query"], func_args.get("max_results", 10))
                    elif func_name == "run_cmd":
                        tool_output = tools_api.run_cmd(func_args["cmd"])
                    else:
                        tool_output = f"Unknown tool: {func_name}"
                except Exception as e:
                    tool_output = f"Tool Error: {str(e)}"
                    
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": func_name,
                    "content": tool_output
                })
                
                # Optionally save patch generation for unified diff tools implicitly to OS
                if func_name == "apply_patch" and "successfully" in tool_output.lower():
                    try:
                        os.makedirs(".patches", exist_ok=True)
                        from datetime import datetime
                        timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
                        safe_name = func_args['path'].replace('/', '_').replace('\\', '_')
                        patch_log = os.path.join(".patches", f"{safe_name}.{timestamp}.patch")
                        with open(patch_log, "w", encoding="utf-8") as f:
                            f.write(func_args["unified_diff"])
                    except Exception:
                        pass
        else:
            # ReAct conversational loop hook for empty uncalled tool structures
            messages.append({"role": "user", "content": "Please continue with tool usage or explicitly output 'DONE' if the task for this step is fully resolved."})

    if not did_modify_target:
        state["errors"] = [f"Executor did not modify planned target file: {path}"]

    # Log diff state securely into Graph DAG node progression
    if new_diff_log:
        state["diffs"].append({
            "path": path,
            "snippet": new_diff_log[:2000]
        })
    if last_mod_content:
        state["last_modified"] = {"path": path, "content": last_mod_content}
        
    state["current_step"] += 1

    return state
