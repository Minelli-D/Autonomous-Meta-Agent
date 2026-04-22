from tools.shell_tools import run_command

def build_step(state, repo_root):

    code, output = run_command(f"cd {repo_root} && npx next build")
    state["build_output"] = output
    state["build_exit_code"] = code
    return state