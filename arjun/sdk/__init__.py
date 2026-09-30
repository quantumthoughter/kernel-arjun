"""Kernel-Arjun SDK — the durable-execution kernel for long-horizon AI agents.

Quickstart:

    from arjun.sdk import Arjun

    k = Arjun(workspace="./job", backend="openai")
    goal = k.goal("Write a haiku about archery",
                  dod="haiku.txt exists with a 3-line haiku",
                  max_tokens=20000)
    result = k.run(goal)
    print(result.status, result.meter.words)

Bring your own model:

    k = Arjun(backend=Backend(kind="ollama", base_url="http://127.0.0.1:11434",
                              models={"executor": "qwen2.5-coder:7b", ...}))

Bring your own verifier:

    from arjun.sdk.verifiers import word_count_gate
    k = Arjun(workspace="./book", verifier=word_count_gate("book/ch1.md", 3000))
"""
from .backends import Backend
from .client import Arjun, GoalHandle, RunResult
from .verifiers import (
    AllOf,
    AnyOf,
    DeterministicVerifier,
    ModelVerifier,
    canon_gate,
    file_exists_gate,
    shell_gate,
    word_count_gate,
)

__all__ = [
    "Arjun",
    "GoalHandle",
    "RunResult",
    "Backend",
    "ModelVerifier",
    "DeterministicVerifier",
    "AllOf",
    "AnyOf",
    "word_count_gate",
    "file_exists_gate",
    "shell_gate",
    "canon_gate",
]
