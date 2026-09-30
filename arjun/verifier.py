from __future__ import annotations

import json
import re

from .context import build_goal_verifier_messages, build_verifier_messages


def parse_json_block(text: str) -> dict | None:
    if not text:
        return None
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            obj = json.loads(match.group(0))
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            return None
    return None


class Verifier:
    def __init__(self, router):
        self.router = router

    def verify_task(self, goal: dict, task: dict, steps: list[dict], artifacts: list[dict]) -> dict:
        messages = build_verifier_messages(goal, task, steps, artifacts)
        resp = self.router.complete("verifier", messages)
        verdict = parse_json_block(resp.content)
        if not isinstance(verdict, dict) or "pass" not in verdict:
            return {"pass": False, "reason": "verifier output unparseable", "missing": [], "raw": resp.content[:300]}
        verdict["pass"] = bool(verdict.get("pass"))
        return verdict

    def verify_goal(self, goal: dict, task_counts: dict, artifacts: list[dict]) -> dict:
        messages = build_goal_verifier_messages(goal, task_counts, artifacts)
        resp = self.router.complete("verifier", messages)
        verdict = parse_json_block(resp.content)
        if not isinstance(verdict, dict) or "pass" not in verdict:
            return {"pass": False, "reason": "goal verifier output unparseable", "missing": [], "raw": resp.content[:300]}
        verdict["pass"] = bool(verdict.get("pass"))
        return verdict
