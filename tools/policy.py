import os

FORBIDDEN_DIRS = {"node_modules", ".git", ".next", ".turbo", "dist", "build", "out"}
FORBIDDEN_FILES = {
    ".env", ".env.local", ".env.development", ".env.production", 
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml"
}
ALLOWED_COMMANDS = {
    "npx next build", "npm run build", "pnpm build", "yarn build", 
    "npx eslint", "npm run lint"
}

class SecurityPolicyError(Exception):
    """Exception raised for policy violations (sandbox, forbidden paths, etc)."""
    pass

def check_path_policy(repo_root: str, path: str) -> str:
    """
    Enforces the repo-root sandbox and prevents access to forbidden paths/files.
    Returns the absolute safe path.
    """
    repo_root = os.path.abspath(repo_root)
    
    # Normalize path separators and prevent absolute paths masking as relative
    if os.path.isabs(path):
        full_path = os.path.normpath(path)
    else:
        full_path = os.path.abspath(os.path.join(repo_root, path))
    
    # 1. Sandbox enforcement
    if not full_path.startswith(repo_root + os.sep) and full_path != repo_root:
        raise SecurityPolicyError(f"Sandbox violation: {path} is outside the repository root.")

    # Get the relative part for policy checking
    rel_path = os.path.relpath(full_path, repo_root)
    parts = rel_path.split(os.sep)
    
    # 2. Directory checks
    for part in parts:
        if part in FORBIDDEN_DIRS:
            raise SecurityPolicyError(f"Forbidden directory access: {part}")
            
    # 3. File checks
    basename = os.path.basename(full_path)
    if basename in FORBIDDEN_FILES or basename.endswith("-lock.json") or basename.endswith(".lock"):
        raise SecurityPolicyError(f"Forbidden file access: {basename}")
        
    return full_path

def check_cmd_policy(cmd: str) -> str:
    """
    Restricts shell commands to an allowed whitelist.
    """
    cmd = cmd.strip()
    if not any(cmd.startswith(allowed) for allowed in ALLOWED_COMMANDS):
        raise SecurityPolicyError(f"Command not allowed: '{cmd}'. Must start with an allowed prefix.")
    return cmd
