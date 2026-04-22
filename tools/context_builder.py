import os
from tools.file_tools import safe_join, read_file

def build_context(state, repo_root, step, max_files=5, max_chars=10000):
    context_files = []
    snippets = []
    
    # Gather layout, globals.css, and 1-2 pages based on project metadata
    meta = state.get("project_metadata", {})
    router_base = meta.get("router_base", "app")
    
    candidates = [
        f"{router_base}/layout.tsx",
        f"{router_base}/globals.css",
        "globals.css",
        "styles/globals.css",
        f"{router_base}/page.tsx"
    ]
    
    # Look for files referenced in description
    words = step.get("description", "").split()
    for w in words:
        w_clean = w.strip(".,`'\";[]{}()")
        if "." in w_clean and w_clean.split(".")[-1] in ["js", "ts", "jsx", "tsx", "css"]:
            candidates.append(w_clean)
            
    # Check common folders for closest UI components
    for folder in meta.get("common_folders", []):
        if "component" in folder.lower() or "ui" in folder.lower():
            try:
                components_dir = safe_join(repo_root, folder)
                if os.path.exists(components_dir) and os.path.isdir(components_dir):
                    for root, _, files in os.walk(components_dir):
                        for f in files:
                            if f.endswith((".tsx", ".jsx", ".ts", ".js")):
                                rel = os.path.relpath(os.path.join(root, f), repo_root)
                                candidates.append(rel)
                        break # Only top level for now
            except Exception:
                pass

    total_chars = 0
    seen = set()
    
    for cand in candidates:
        if cand in seen:
            continue
        seen.add(cand)
        
        try:
            full_path = safe_join(repo_root, cand)
            if os.path.isfile(full_path):
                content = read_file(full_path)
                snippet_len = len(content)
                if total_chars + snippet_len > max_chars:
                    rem = max_chars - total_chars
                    if rem > 200:
                        snippets.append(f"--- {cand} (truncated) ---\n{content[:rem]}\n")
                        total_chars += rem
                    break # Reached character limit
                else:
                    snippets.append(f"--- {cand} ---\n{content}\n")
                    total_chars += snippet_len
                    context_files.append(cand)
                    if len(context_files) >= max_files:
                        break # Reached file limit
        except Exception:
            pass
            
    if not snippets:
        return "No reference context found."
        
    return "\n".join(snippets)
