from langgraph.graph import END, StateGraph

from agents.executor import executor
from agents.fixer import fixer
from agents.planner import planner
from agents.reviewer import reviewer
from plans.executor import plan_executor
from state import AgentState
from tools.build import build_step


def build_graph(repo_root, plan_mode: bool = False):
    workflow = StateGraph(AgentState)

    if plan_mode:
        workflow.add_node("plan_executor", lambda s: plan_executor(s, repo_root))
        workflow.add_node("build", lambda s: build_step(s, repo_root))
        workflow.add_node("fixer", lambda s: fixer(s, repo_root))
        workflow.add_node("reviewer", lambda s: reviewer(s, repo_root))

        workflow.set_entry_point("plan_executor")
        workflow.add_edge("plan_executor", "build")

        def after_build_plan(state):
            if state.get("build_exit_code", 0) != 0 and (state.get("fix_attempts") or 0) < 3:
                return "fixer"
            return "reviewer"

        workflow.add_conditional_edges("build", after_build_plan)
        workflow.add_edge("fixer", "build")
        workflow.add_edge("reviewer", END)
        return workflow.compile()

    workflow.add_node("planner", planner)
    workflow.add_node("executor", lambda s: executor(s, repo_root))
    workflow.add_node("build", lambda s: build_step(s, repo_root))
    workflow.add_node("fixer", lambda s: fixer(s, repo_root))
    workflow.add_node("reviewer", lambda s: reviewer(s, repo_root))

    workflow.set_entry_point("planner")
    workflow.add_edge("planner", "executor")

    def should_continue(state):
        if state["current_step"] < len(state["plan"]):
            return "executor"
        return "build"

    workflow.add_conditional_edges("executor", should_continue)

    def after_build(state):
        if state.get("build_exit_code", 0) != 0 and (state.get("fix_attempts") or 0) < 3:
            return "fixer"
        return "reviewer"

    workflow.add_conditional_edges("build", after_build)
    workflow.add_edge("fixer", "build")
    workflow.add_edge("reviewer", END)

    return workflow.compile()
