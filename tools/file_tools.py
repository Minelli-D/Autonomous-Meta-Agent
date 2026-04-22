import os

def safe_join(repo_root: str, relative_path: str) -> str:
    repo_root = os.path.abspath(repo_root)
    full = os.path.abspath(os.path.join(repo_root, relative_path))
    if not full.startswith(repo_root + os.sep):
        raise ValueError(f"Unsafe path: {relative_path}")
    return full

def read_file(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def write_file(path: str, content: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def list_directory(path: str):
    return os.listdir(path)