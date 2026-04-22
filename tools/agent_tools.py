import os
import json
import subprocess
import tempfile
import difflib

from tools.policy import check_path_policy, check_cmd_policy, SecurityPolicyError
from tools.file_tools import read_file as _read_file, write_file as _write_file

class AgentTools:
    """
    Exposes minimal, carefully constrained python tools.
    All path modifications go through the SecurityPolicyError guards.
    """
    def __init__(self, repo_root, dry_run=False):
        self.repo_root = os.path.abspath(repo_root)
        self.dry_run = dry_run

    def list_dir(self, path: str) -> str:
        try:
            full = check_path_policy(self.repo_root, path)
            if not os.path.exists(full): return f"Error: Directory '{path}' not found."
            items = os.listdir(full)
            return json.dumps(items)
        except Exception as e:
            return f"Error: {e}"

    def read_file(self, path: str) -> str:
        try:
            full = check_path_policy(self.repo_root, path)
            if not os.path.exists(full): return f"Error: File '{path}' not found."
            return _read_file(full)
        except Exception as e:
            return f"Error: {e}"

    def write_file(self, path: str, content: str) -> str:
        try:
            full = check_path_policy(self.repo_root, path)
            if not self.dry_run:
                _write_file(full, content)
            return f"Successfully wrote to {path}"
        except Exception as e:
            return f"Error: {e}"

    def apply_patch(self, path: str, unified_diff: str) -> str:
        try:
            full = check_path_policy(self.repo_root, path)
            with tempfile.NamedTemporaryFile("w", delete=False, suffix=".patch") as pf:
                pf.write(unified_diff)
                patch_file = pf.name

            target = full
            temp_copy = None
            if self.dry_run:
                # On dry run, we clone the file locally if it exists, to simulate the patch application
                if os.path.exists(full):
                    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".tsx") as tf:
                        tf.write(_read_file(full))
                        temp_copy = tf.name
                    target = temp_copy
                else:
                    return f"Error: file {path} does not exist to apply a patch to."

            try:
                # Apply with standard strict p1 params
                res = subprocess.run(
                    ["patch", "-p1", "--no-backup-if-mismatch", "--force", target, patch_file], 
                    cwd=self.repo_root, capture_output=True, text=True
                )
                if res.returncode == 0:
                    return f"Patch applied successfully to {path}.\nOutput: {res.stdout.strip()}"
                else:
                    return f"Failed to apply patch to {path}.\nOutput: {res.stdout.strip()}\nError: {res.stderr.strip()}"
            finally:
                if os.path.exists(patch_file): os.remove(patch_file)
                if temp_copy and os.path.exists(temp_copy): os.remove(temp_copy)
        except Exception as e:
            return f"Error: {e}"

    def search_text(self, query: str, max_results: int = 10) -> str:
        try:
            results = []
            for root, dirs, files in os.walk(self.repo_root):
                # Filter out forbidden subdirectories early for speed
                dirs[:] = [d for d in dirs if d not in {"node_modules", ".git", ".next", "dist", "build", "out", ".turbo"}]
                for f in files:
                    if f.endswith((".ts", ".tsx", ".js", ".jsx", ".css", ".json", ".md", ".html")):
                        full_path = os.path.join(root, f)
                        rel_path = os.path.relpath(full_path, self.repo_root)
                        try:
                            with open(full_path, "r", encoding="utf-8") as filedata:
                                content = filedata.read()
                                if query in content:
                                    results.append(f"Found in {rel_path}")
                                    if len(results) >= max_results:
                                        return json.dumps(results)
                        except Exception:
                            # Skip unreadable
                            pass
            return json.dumps(results)
        except Exception as e:
            return f"Error: {e}"

    def run_cmd(self, cmd: str) -> str:
        try:
            safe_cmd = check_cmd_policy(cmd)
            if self.dry_run:
                return f"[DRY RUN] Would execute: {safe_cmd}"
            res = subprocess.run(safe_cmd, shell=True, cwd=self.repo_root, capture_output=True, text=True)
            return f"Exit code: {res.returncode}\nStdout: {res.stdout.strip()}\nStderr: {res.stderr.strip()}"
        except Exception as e:
            return f"Error: {e}"
