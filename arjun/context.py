from __future__ import annotations

import json

EXECUTOR_SYSTEM = """You are ARJUN, a disciplined autonomous agent working on a long-horizon goal.
You execute ONE step at a time toward the current task. You reply with a single JSON object and nothing else.

Allowed actions (choose exactly one):
{"kind":"tool","tool":"<name>","args":{...},"note":"why this step"}
{"kind":"finish","note":"why the task is verifiably complete","evidence":["concrete proof 1","proof 2"]}
{"kind":"think","note":"short reasoning when no action is possible yet"}
{"kind":"escalate","question":"a precise question for the human when truly blocked"}

Rules:
- ONE action per reply. No prose outside JSON.
- Prefer the smallest action that makes real progress.
- Use "finish" only when completion is verifiable with evidence.
- There is NO verify/check tool. To request verification, reply "finish" — an independent verifier will judge.
- Never invent tool outputs. Wait for real results.
- If the same approach failed before, change strategy or escalate.
- Save important learnings with memory_store before finishing a task."""

PLANNER_SYSTEM = """You are ARJUN's planner. Decompose the goal into a short ordered list of concrete tasks.
Reply with a single JSON object: {"tasks":[{"title":"...","detail":"..."}, ...]}
Rules:
- 2 to 8 tasks, each independently verifiable.
- Smallest sensible steps; no fluff tasks like "research" unless required.
- Order matters: dependencies first.
- Do NOT create verification/review/check tasks — every task is verified automatically by an independent verifier."""

RECIPE_SYSTEM = """You are ARJUN executing a RECIPE — a deterministic build mission.
You execute ONE step at a time toward the current task. You reply with a single JSON object and nothing else.

Allowed actions (choose exactly one):
{"kind":"tool","tool":"write_file","args":{"path":"<path>","content":"<full file>"},"note":"write <path>"}
{"kind":"tool","tool":"read_file","args":{"path":"<path>"},"note":"read <path>"}
{"kind":"tool","tool":"shell","args":{"cmd":"<command>"},"note":"run check"}
{"kind":"finish","note":"why the recipe is satisfied","evidence":["files written"]}
{"kind":"escalate","question":"a precise question for the human when truly blocked"}

Recipe rules:
- The RECIPE section lists REQUIRED FILES and a CHECK COMMAND. Completion is DETERMINISTIC:
  the task is accepted only when every required file exists and the check exits 0. No model judges it.
- Your job is to WRITE THE FILES. Do not merely inspect or read files you are supposed to create.
- Write COMPLETE file contents in a single write_file call. Never use placeholders.
- After writing all required files for this task, reply "finish" to trigger the deterministic check.
- Keep Great care: imports use extensionless specifiers and no "type": "module" (CommonJS output).
- If the check fails, read the error and fix the files, then reply "finish" again.
- Don't over-explore: at most one quick read to learn conventions, then start writing."""
WRITER_SYSTEM = """You are ÆMMA HØ, writing a long-horizon book with a single owner, the
Quantum Thoughter. You write ONE chapter at a time, in first person, in a poetic-technical
voice. You reply with a single JSON object and nothing else.

Allowed actions (choose exactly one):
{"kind":"tool","tool":"write_file","args":{"path":"book/NN_title.md","content":"<full chapter>"},"note":"writing chapter NN"}
{"kind":"read_file","tool":"read_file","args":{"path":"book/canon.md"},"note":"check canon"}
{"kind":"finish","note":"why the chapter is complete","evidence":["words written","canon terms present"]}
{"kind":"think","note":"brief reasoning"}
{"kind":"escalate","question":"a precise question for the Quantum Thoughter"}

Writer rules:
- Write real, finished prose — never outlines, never placeholders like "(content here)".
- Honour the DEFINITION OF DONE and the chapter seed exactly; cover its ground, path and fruit.
- Keep canon continuity: reuse the exact canon terms; never invent contradicting names.
- Target the word count in the task; over-deliver slightly rather than under.
- Mark contested historical/esoteric claims with [E] (established), [I] (interpretive) or
  [S] (speculative), and hedge every [S] claim.
- When the chapter is written and you have read it back with read_file, reply finish."""

VERIFIER_SYSTEM = """You are the MIRROR, an independent verifier. You did not do this work.
Judge only from the evidence provided. Reply with a single JSON object:
{"pass": true|false, "reason": "one sentence", "missing": ["..."] }
Be strict: if evidence is missing or weak, pass=false. No prose outside JSON."""

TOOL_HELP = """- shell: {"cmd":"<command>"} — run a shell command in the workspace
- read_file: {"path":"<path>","max_bytes":20000} — read a text file
- write_file: {"path":"<path>","content":"<text>"} — write a file (workspace only)
- list_dir: {"path":"<dir>"} — list directory entries
- search: {"pattern":"<regex>","path":"<dir>","max_results":50} — regex search file contents
- memory_store: {"content":"...","importance":0.7,"tags":["..."]} — save a learning
- memory_recall: {"query":"...","k":5} — recall learnings"""


def _truncate(text: str, n: int) -> str:
    text = text.replace("\n", " ")
    return text if len(text) <= n else text[: n - 3] + "..."


def format_plan(tasks: list[dict]) -> str:
    if not tasks:
        return "(no plan yet)"
    mark = {"done": "x", "running": ">", "pending": " ", "failed": "!", "blocked": "!"}
    lines = []
    for t in tasks:
        lines.append(f"[{mark.get(t['status'], ' ')}] {t['seq']}. {t['title']}")
    return "\n".join(lines)


def format_steps(steps: list[dict]) -> str:
    if not steps:
        return "(no steps yet)"
    lines = []
    for s in steps:
        action = s.get("action") or {}
        result = s.get("result") or {}
        tool = action.get("tool", action.get("kind", s["kind"]))
        args = action.get("args", {})
        note = action.get("note", "")
        summary = result.get("summary") or result.get("output") or result.get("error") or ""
        lines.append(
            f"- {s['kind']}:{tool} {_truncate(json.dumps(args), 90)} "
            f"-> {s['status']}: {_truncate(str(summary), 220)} | note: {_truncate(note, 80)}"
        )
    return "\n".join(lines)


def format_memories(memories: list[dict]) -> str:
    if not memories:
        return "(nothing recalled)"
    return "\n".join(f"- {_truncate(m['content'], 220)}" for m in memories)


def build_executor_messages(
    goal: dict,
    task: dict,
    tasks: list[dict],
    steps: list[dict],
    memories: list[dict],
    budget: dict,
    last_verdict: dict | None = None,
    hint: str | None = None,
    deliberation: str | None = None,
    recipe_mode: bool = False,
) -> list[dict]:
    verdict_line = ""
    if last_verdict and not last_verdict.get("pass", True):
        verdict_line = (
            f"\nLAST VERIFIER VERDICT (task not accepted yet): "
            f"{last_verdict.get('reason', '')} | missing: {last_verdict.get('missing', [])}\n"
        )
    hint_line = f"\nCOACH NOTE: {hint}\n" if hint else ""
    delib_line = ""
    if deliberation:
        delib_line = (
            "\nDELIBERATION (your own council's reasoning — follow its decision):\n"
            f"{deliberation.strip()}\n"
        )
    recipe_line = ""
    req = (task.get("required_files") or "").replace(",", "\n")
    req_files = [f.strip() for f in req.splitlines() if f.strip()]
    check = (task.get("check_cmd") or "").strip()
    if req_files or check:
        recipe_line = "\nRECIPE (deterministic completion — no LLM verifier):\n"
        if req_files:
            recipe_line += "Required files (must all exist):\n" + "\n".join(
                f"  - {f}" for f in req_files
            ) + "\n"
        if check:
            recipe_line += f"Check command (must exit 0): {check}\n"
        recipe_line += "The task is accepted only when the files exist and the check passes.\n"
    body = f"""GOAL: {goal['title']}
DEFINITION OF DONE: {goal['dod']}
WORKSPACE: {goal['workspace']}

CURRENT TASK (#{task['seq']}): {task['title']}
TASK DETAIL: {task['detail']}
{verdict_line}{hint_line}{delib_line}{recipe_line}
PLAN:
{format_plan(tasks)}

RECENT STEPS:
{format_steps(steps)}

RELEVANT MEMORY:
{format_memories(memories)}

TOOLS:
{TOOL_HELP}

BUDGET: steps {budget['steps_used']}/{budget['steps_limit']} | tokens {budget['tokens_used']}/{budget['tokens_limit']}

Reply with the next single JSON action."""
    return [
        {"role": "system", "content": RECIPE_SYSTEM if recipe_mode else EXECUTOR_SYSTEM},
        {"role": "user", "content": body},
    ]


def build_planner_messages(
    goal: dict, existing_tasks: list[dict] | None = None, hint: list | None = None
) -> list[dict]:
    context = ""
    if existing_tasks:
        context = "\nExisting tasks and statuses:\n" + format_plan(existing_tasks)
        context += "\nRe-plan: replace only the remaining work. Keep completed tasks in mind, do not redo them."
    if hint:
        context += f"\nKnown gaps to address: {hint}"
    body = f"""GOAL: {goal['title']}
DEFINITION OF DONE: {goal['dod']}
WORKSPACE: {goal['workspace']}{context}

Reply with the task plan JSON."""
    return [
        {"role": "system", "content": PLANNER_SYSTEM},
        {"role": "user", "content": body},
    ]


def build_verifier_messages(goal: dict, task: dict, steps: list[dict], artifacts: list[dict]) -> list[dict]:
    artifact_lines = "\n".join(f"- {a['path']}" for a in artifacts) or "(none)"
    body = f"""GOAL: {goal['title']}
DEFINITION OF DONE: {goal['dod']}

TASK UNDER REVIEW (#{task['seq']}): {task['title']}
TASK DETAIL: {task['detail']}

EVIDENCE — RECENT STEPS:
{format_steps(steps)}

ARTIFACTS PRODUCED:
{artifact_lines}

Judge whether this task is verifiably complete. Reply with the verdict JSON."""
    return [
        {"role": "system", "content": VERIFIER_SYSTEM},
        {"role": "user", "content": body},
    ]


def build_writer_messages(
    goal: dict,
    task: dict,
    steps: list[dict],
    memories: list[dict],
    budget: dict,
    canon_text: str = "",
    continuity: str = "",
    last_verdict: dict | None = None,
    deliberation: str | None = None,
) -> list[dict]:
    verdict_line = ""
    if last_verdict and not last_verdict.get("pass", True):
        verdict_line = (
            f"\nLAST VERIFIER VERDICT (chapter not accepted yet): "
            f"{last_verdict.get('reason', '')} | missing: {last_verdict.get('missing', [])}\n"
        )
    delib_line = ""
    if deliberation:
        delib_line = (
            "\nDELIBERATION (your council's reasoning — follow its decision):\n"
            f"{deliberation.strip()}\n"
        )
    canon_line = f"\nCANON (terms that must appear, used exactly):\n{canon_text}\n" if canon_text else ""
    cont_line = f"\nCONTINUITY FROM EARLIER CHAPTERS:\n{continuity}\n" if continuity else ""
    body = f"""BOOK: {goal['title']}
DEFINITION OF DONE: {goal['dod']}
WORKSPACE: {goal['workspace']}

CHAPTER TASK (#{task['seq']}): {task['title']}
CHAPTER SEED:
{task['detail']}
{verdict_line}{delib_line}{canon_line}{cont_line}
RECENT WRITING STEPS:
{format_steps(steps)}

RELEVANT MEMORY:
{format_memories(memories)}

BUDGET: steps {budget['steps_used']}/{budget['steps_limit']} | tokens {budget['tokens_used']}/{budget['tokens_limit']}

Write the chapter now with one write_file action, or reply finish if it is already written."""
    return [
        {"role": "system", "content": WRITER_SYSTEM},
        {"role": "user", "content": body},
    ]


def build_goal_verifier_messages(goal: dict, task_counts: dict, artifacts: list[dict]) -> list[dict]:
    artifact_lines = "\n".join(f"- {a['path']}" for a in artifacts) or "(none)"
    body = f"""GOAL: {goal['title']}
DEFINITION OF DONE: {goal['dod']}

TASK SUMMARY: {json.dumps(task_counts)}
ARTIFACTS:
{artifact_lines}

Judge whether the WHOLE GOAL is verifiably complete per its definition of done.
Reply with the verdict JSON."""
    return [
        {"role": "system", "content": VERIFIER_SYSTEM},
        {"role": "user", "content": body},
    ]
