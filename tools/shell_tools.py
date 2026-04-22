import subprocess

def run_command(cmd: str):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    out = (result.stdout or "") + (result.stderr or "")
    return result.returncode, out