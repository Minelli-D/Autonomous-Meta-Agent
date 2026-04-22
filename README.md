# Autonomous Next.js Meta-Agent

This project was designed and implemented through a **collaborative workflow between a human developer and AI systems**.

Rather than being auto-generated, the AI was used as an **engineering assistant** to accelerate development, improve code quality, and explore design solutions.

---

## 🚀 About the Project

This project explores the design and implementation of a **code-modifying AI agent**.

The goal is to understand how agent-based systems can operate on real codebases in a controlled and deterministic way, applying structured changes while preserving existing project architecture.

The system is built around a multi-step workflow (planner → executor → reviewer → fixer) to simulate a reliable development process with validation and feedback loops.

---

## 🧠 AI Collaboration Approach

This project was developed using a **human-in-the-loop AI workflow**, where:

- The **developer defined architecture, constraints, and decisions**
- The **AI assisted with implementation, refactoring, and iteration**
- All outputs were **reviewed, validated, and integrated manually**

### AI Contributions Included:
- Code generation for repetitive or boilerplate logic
- Refactoring suggestions and improvements
- Test case generation
- Architectural brainstorming
- Debugging assistance

### Human Responsibilities:
- System design and architecture
- Defining constraints and guardrails
- Reviewing and validating all generated code
- Final implementation decisions

---

## ⚙️ Tech Stack

### Core
- Python 3.12

### AI & Agent Orchestration
- LangGraph (stateful agent workflow orchestration)
- OpenAI SDK (LLM interaction)

### Architecture
- Multi-agent pipeline (Planner → Executor → Reviewer → Fixer)
- Graph-based execution model
- Stateful agent system

### Data & Validation
- Pydantic (schema validation and state management)
- JSON Patch (controlled file modifications)

### Utilities
- httpx (async HTTP client)
- orjson (high-performance JSON parsing)
- PyYAML (configuration)
- tenacity (retry strategies)
- tqdm (progress tracking)
---

## 🏗️ Development Philosophy

This project follows a **controlled AI-assisted development model**:

- ✅ AI is used as a **tool**, not a replacement
- ✅ All code passes **human validation**
- ✅ Emphasis on **maintainability and correctness**
- ✅ Structured workflows (planner → executor → reviewer)

---

## 📬 Notes

This repository is part of an ongoing exploration into:
- AI-assisted software development
- Agent-based systems
- Developer productivity optimization

---

## How to Run
```bash
python main.py "Extract the header from app/page.tsx into a component and reuse it."
```

If you want to run safely to preview what it will generate:
```bash
python main.py --dry-run "Extract the header from app/page.tsx into a component and reuse it."
```

## Sample Run (Expected Output)
```json
{`
  "task": "Add /login page matching existing layout + styling patterns.",
  "plan": [
    {
      "action": "create_file",
      "path": "app/login/page.tsx",
      "description": "Create a new login page component resembling the current page.tsx layout"
    }
  ],
  "steps_run": 1,
  "diffs": [
    {
      "path": "app/login/page.tsx",
      "snippet": "--- app/login/page.tsx\n+++ app/login/page.tsx\n@@ -1,0 +1,50 @@\n..."
    }
  ],
  "build_exit_code": 0,
  "build_output": "Ready in 1432ms\nRoute (app)   Size     First Load JS\n┌ ○ /         289 B    84 kB\n...",
  "fix_attempts": 0,
  "reviewer_decision": "Approved",
  "timestamp": "2026-02-26T21:40:00"
}
```

## Logs
Detailed logs containing structural reasoning, standard unified diffs, and DAG node flow sequences are exported continuously into `.logs/task-YYYY-MM-DD.json`

## Plan DSL Sample + Smoke Test
Use the included strict plan sample:
```bash
.venv/bin/python main.py --plan plans/examples/sample_plan.json --dry-run
```

If you want to provide analysis/context and let LLM decide `action` + `path` within a strict allowlist, use:
```bash
.venv/bin/python main.py --plan plans/examples/hybrid_llm_step_plan.json --dry-run
```

Run the lightweight executor smoke test (no planner/build/reviewer):
```bash
.venv/bin/python scripts/smoke_plan.py --plan plans/examples/sample_plan.json --dry-run
```
main.py --plan plans/examples/account-creation.json