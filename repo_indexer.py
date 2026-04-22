import os
import json

EXCLUDED_DIRS = {"node_modules", ".git", ".next", "dist", "build", "out", ".turbo"}


def detect_project_metadata(repo_root: str):
    metadata = {}

    # Basic detection
    metadata["has_app_router"] = os.path.exists(os.path.join(repo_root, "app"))
    metadata["has_pages_router"] = os.path.exists(os.path.join(repo_root, "pages"))
    metadata["has_src_folder"] = os.path.exists(os.path.join(repo_root, "src"))
    metadata["has_tailwind"] = any(
        os.path.exists(os.path.join(repo_root, f"tailwind.config.{ext}"))
        for ext in ["js", "ts", "mjs", "cjs"]
    )
    metadata["has_eslint"] = any(
        os.path.exists(os.path.join(repo_root, f))
        for f in [".eslintrc", ".eslintrc.json", ".eslintrc.js", ".eslintrc.cjs", ".eslintrc.yaml", ".eslintrc.yml", "eslint.config.js", "eslint.config.mjs", "eslint.config.cjs"]
    )
    metadata["has_prettier"] = any(
        os.path.exists(os.path.join(repo_root, f))
        for f in [".prettierrc", ".prettierrc.json", ".prettierrc.js", ".prettierrc.cjs", ".prettierrc.yaml", ".prettierrc.yml", "prettier.config.js", "prettier.config.cjs"]
    )
    metadata["is_typescript"] = os.path.exists(os.path.join(repo_root, "tsconfig.json"))

    # Router base (important for Next.js)
    # Supports src/app, src/pages, app, pages
    router_base = None
    if metadata["has_src_folder"] and os.path.exists(os.path.join(repo_root, "src", "app")):
        router_base = "src/app"
    elif metadata["has_src_folder"] and os.path.exists(os.path.join(repo_root, "src", "pages")):
        router_base = "src/pages"
    elif metadata["has_app_router"]:
        router_base = "app"
    elif metadata["has_pages_router"]:
        router_base = "pages"
    metadata["router_base"] = router_base

    # Detect exact router type explicitely
    if metadata["has_app_router"]:
        metadata["router_type"] = "app"
    elif metadata["has_pages_router"]:
        metadata["router_type"] = "pages"
    else:
        metadata["router_type"] = "unknown"

    # Detect common folders (helps planner avoid inventing structure)
    common = []
    for candidate in ["components", "ui", "lib", "hooks", "styles"]:
        if os.path.exists(os.path.join(repo_root, candidate)):
            common.append(candidate)
        if metadata["has_src_folder"] and os.path.exists(os.path.join(repo_root, "src", candidate)):
            common.append(f"src/{candidate}")
    metadata["common_folders"] = common

    # Detect dependencies (helps decide auth/ui libs)
    metadata["dependencies"] = []
    pkg = os.path.join(repo_root, "package.json")
    if os.path.exists(pkg):
        try:
            with open(pkg, "r", encoding="utf-8") as f:
                package = json.load(f)
            deps = package.get("dependencies", {}) or {}
            dev = package.get("devDependencies", {}) or {}
            metadata["dependencies"] = sorted(set(list(deps.keys()) + list(dev.keys())))
        except Exception:
            pass

    return metadata


def generate_repo_map(root: str, depth: int = 3):
    tree = []
    root = os.path.abspath(root)

    for root_dir, dirs, files in os.walk(root):
        # prune excluded dirs
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]

        level = root_dir.replace(root, "").count(os.sep)
        if level > depth:
            continue

        indent = "  " * level
        tree.append(f"{indent}{os.path.basename(root_dir)}/")

        # keep map compact: ignore huge lock files etc.
        files_sorted = sorted(files)
        for f in files_sorted:
            if f in {"package-lock.json", "yarn.lock", "pnpm-lock.yaml"}:
                continue
            tree.append(f"{indent}  {f}")

    return "\n".join(tree)