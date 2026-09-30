from __future__ import annotations

from dataclasses import dataclass, field

from .models import ModelError, ModelResponse

# The Council of the house: Thoth (plan), Murugan (craft), Sisi (guard), Dakini (act).
# Each pass is a real model call whose answer AND reasoning trace are kept.

COUNCIL = {
    "thoth": (
        "You are THOTH, the planner of Kernel-Arjun. Think slowly and precisely. "
        "Given the goal, the current task, the plan, and recent steps, decide what this "
        "task truly needs: the single smallest next action that makes real, verifiable "
        "progress. Name the step, the tool, and the exact expected result. Think only; "
        "do not act yet."
    ),
    "murugan": (
        "You are MURUGAN, the craftsman of Kernel-Arjun. Given Thoth's plan, think about "
        "how to do it well: the exact content, form, or command; the pitfalls; what "
        "'done' concretely looks like. Be concrete and specific. Think only; do not act yet."
    ),
    "sisi": (
        "You are SISI, the guardian of Kernel-Arjun. Given the plan and the craft, hunt for "
        "risk: contradictions with earlier work or canon, lost continuity, safety violations, "
        "duplicated effort, or loops. State any constraint the next action must respect. "
        "Think only; do not act yet."
    ),
    "dakini": (
        "You are DAKINI, the swift executor of Kernel-Arjun. Synthesise Thoth, Murugan and "
        "Sisi into ONE decision: the single best next action, its exact arguments, and the "
        "concrete evidence that will prove it done. Be decisive and unambiguous."
    ),
}

FAST_ORDER = ["thoth", "dakini"]
FULL_ORDER = ["thoth", "murugan", "sisi", "dakini"]


@dataclass
class Pass:
    agent: str
    content: str
    reasoning: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    reasoning_tokens: int = 0


@dataclass
class CouncilResult:
    transcript: list[Pass] = field(default_factory=list)
    synthesis: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    reasoning_tokens: int = 0

    def as_dict(self) -> dict:
        return {
            "passes": [
                {
                    "agent": p.agent,
                    "content": p.content,
                    "reasoning": p.reasoning,
                    "tokens_in": p.tokens_in,
                    "tokens_out": p.tokens_out,
                    "reasoning_tokens": p.reasoning_tokens,
                }
                for p in self.transcript
            ],
            "synthesis": self.synthesis,
        }

    def transcript_text(self) -> str:
        lines = []
        for p in self.transcript:
            lines.append(f"[{p.agent.upper()}] {p.content.strip()}")
        return "\n".join(lines)


class Council:
    """Multi-pass internal reasoning before an action. A lens over the executor.

    Each pass is a genuine model call; token spend is real and is returned so the
    orchestrator can charge it to the goal's budget.
    """

    def __init__(self, router, cfg):
        self.router = router
        self.cfg = cfg

    def deliberate(
        self, brief: str, depth: int | None = None, boundary: bool = False
    ) -> CouncilResult:
        if boundary and self.cfg.council_full_at_boundary:
            depth = max(depth or 0, len(FULL_ORDER))
        depth = depth or self.cfg.reasoning_depth
        order = FULL_ORDER if depth >= len(FULL_ORDER) else FAST_ORDER
        result = CouncilResult()
        prior = ""
        for agent in order:
            system = COUNCIL[agent]
            user = brief
            if prior:
                user += f"\n\nCOUNCIL SO FAR:\n{prior}"
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ]
            try:
                resp = self.router.complete(
                    "executor", messages, json_mode=False, max_tokens=self.cfg.max_output_tokens
                )
            except (ModelError, TypeError):
                # older clients may not accept max_tokens; retry bare
                resp = self.router.complete("executor", messages, json_mode=False)
            p = Pass(
                agent=agent,
                content=resp.content,
                reasoning=resp.reasoning,
                tokens_in=resp.tokens_in,
                tokens_out=resp.tokens_out,
                reasoning_tokens=resp.reasoning_tokens,
            )
            result.transcript.append(p)
            result.tokens_in += resp.tokens_in
            result.tokens_out += resp.tokens_out
            result.reasoning_tokens += resp.reasoning_tokens
            prior += f"\n[{agent.upper()}] {resp.content.strip()}"
        if result.transcript:
            result.synthesis = result.transcript[-1].content
        return result
