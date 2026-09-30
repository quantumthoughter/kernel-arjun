"""Pluggable verifiers.

A verifier decides whether a task's evidence is sufficient. The kernel ships
with:
  - ModelVerifier   the MIRROR — an independent model judges the evidence
  - DeterministicVerifier  a callable gate (word count, tests, canon, ...)
  - AllOf           every child must pass
  - AnyOf           at least one child must pass

A verifier is any object with signature:
    verify(goal: dict, task: dict, steps: list[dict], artifacts: list[dict]) -> dict
returning at least {"pass": bool, "reason": str}.

Model-agnostic and domain-agnostic: bring your own judge.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable

from ..context import build_goal_verifier_messages, build_verifier_messages
from ..models import ModelError
from ..verifier import parse_json_block


class ModelVerifier:
    """The default MIRROR: a different model judges the work."""

    def __init__(self, router, role: str = "verifier"):
        self.router = router
        self.role = role

    def verify(self, goal, task, steps, artifacts) -> dict:
        messages = build_verifier_messages(goal, task, steps, artifacts)
        resp = self.router.complete(self.role, messages)
        verdict = parse_json_block(resp.content)
        if not isinstance(verdict, dict) or "pass" not in verdict:
            return {"pass": False, "reason": "verifier output unparseable",
                    "missing": [], "raw": resp.content[:300]}
        verdict["pass"] = bool(verdict.get("pass"))
        return verdict

    def verify_goal(self, goal, task_counts, artifacts) -> dict:
        messages = build_goal_verifier_messages(goal, task_counts, artifacts)
        resp = self.router.complete(self.role, messages)
        verdict = parse_json_block(resp.content)
        if not isinstance(verdict, dict) or "pass" not in verdict:
            return {"pass": False, "reason": "goal verifier output unparseable",
                    "missing": [], "raw": resp.content[:300]}
        verdict["pass"] = bool(verdict.get("pass"))
        return verdict


class DeterministicVerifier:
    """A pure function gate. `fn(goal, task, steps, artifacts) -> (bool, str)`."""

    def __init__(self, fn: Callable[[dict, dict, list, list], tuple[bool, str]], name: str = "deterministic"):
        self.fn = fn
        self.name = name

    def verify(self, goal, task, steps, artifacts) -> dict:
        try:
            ok, reason = self.fn(goal, task, steps, artifacts)
        except Exception as e:  # a broken verifier must not crash the run
            return {"pass": False, "reason": f"{self.name} verifier error: {e}"}
        return {"pass": bool(ok), "reason": reason, "kind": self.name}


class AllOf:
    def __init__(self, *verifiers):
        self.verifiers = verifiers

    def verify(self, goal, task, steps, artifacts) -> dict:
        reasons = []
        for v in self.verifiers:
            r = v.verify(goal, task, steps, artifacts)
            if not r.get("pass"):
                return r
            reasons.append(r.get("reason", ""))
        return {"pass": True, "reason": " | ".join(reasons)}


class AnyOf:
    def __init__(self, *verifiers):
        self.verifiers = verifiers

    def verify(self, goal, task, steps, artifacts) -> dict:
        reasons = []
        for v in self.verifiers:
            r = v.verify(goal, task, steps, artifacts)
            if r.get("pass"):
                return r
            reasons.append(r.get("reason", ""))
        return {"pass": False, "reason": "none passed: " + " | ".join(reasons)}


# ---- ready-made domain gates ------------------------------------------------

def word_count_gate(path: str, minimum: int) -> DeterministicVerifier:
    def fn(goal, task, steps, artifacts):
        p = Path(goal["workspace"]) / path
        if not p.exists():
            return False, f"{path} missing"
        wc = len(p.read_text().split())
        return wc >= minimum, f"{wc}/{minimum} words"
    return DeterministicVerifier(fn, name=f"word_count:{path}")


def file_exists_gate(path: str) -> DeterministicVerifier:
    def fn(goal, task, steps, artifacts):
        p = Path(goal["workspace"]) / path
        return p.exists(), f"{path} {'exists' if p.exists() else 'missing'}"
    return DeterministicVerifier(fn, name=f"exists:{path}")


def shell_gate(cmd: str, cwd_subdir: str = ".") -> DeterministicVerifier:
    """Gate on a shell command's exit code (e.g. run the test suite)."""
    def fn(goal, task, steps, artifacts):
        cwd = Path(goal["workspace"]) / cwd_subdir
        proc = subprocess.run(cmd, shell=True, cwd=str(cwd), capture_output=True, text=True, timeout=300)
        out = (proc.stdout + proc.stderr).strip()
        return proc.returncode == 0, f"exit {proc.returncode}: {out[-200:]}"
    return DeterministicVerifier(fn, name=f"shell:{cmd[:30]}")


def canon_gate(path: str, terms: list[str]) -> DeterministicVerifier:
    """All terms must appear in the file (case-insensitive)."""
    def fn(goal, task, steps, artifacts):
        p = Path(goal["workspace"]) / path
        if not p.exists():
            return False, f"{path} missing"
        text = p.read_text().lower()
        missing = [t for t in terms if t.lower() not in text]
        return (not missing), ("all terms present" if not missing else f"missing {missing}")
    return DeterministicVerifier(fn, name=f"canon:{path}")
