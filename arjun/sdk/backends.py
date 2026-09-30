"""Backend resolution — pick a model client + router from a config or kwargs.

Supported backends:
  - "openai"  any OpenAI-compatible endpoint (Hive, DeepSeek, vLLM, LM Studio, ...)
  - "ollama"  a local Ollama server
  - "fake"    a scripted model for tests and dry runs

Anything OpenAI-compatible works; the kernel is model-agnostic by design.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from ..models import FakeModel, OllamaClient, OpenAIClient, Router


@dataclass
class Backend:
    kind: str = "openai"
    base_url: str = "https://api-cdn.thehive.ai/api/v3"
    api_key: str = ""
    api_key_env: str = "HIVE_API_KEY"
    timeout: float = 300.0
    models: dict = field(default_factory=lambda: {
        "planner": "deepseek-ai/deepseek-v4.1-flash",
        "executor": "deepseek-ai/deepseek-v4.1-flash",
        "verifier": "zai-org/glm-5.3-flash",
        "compressor": "deepseek-ai/deepseek-v4.1-flash",
    })
    script: list[str] = field(default_factory=list)

    def resolve_key(self) -> str:
        return self.api_key or os.environ.get(self.api_key_env, "")

    def build_client(self):
        if self.kind == "fake":
            return FakeModel(self.script)
        if self.kind == "ollama":
            return OllamaClient(self.base_url, timeout=self.timeout)
        return OpenAIClient(self.base_url, self.resolve_key(), timeout=self.timeout)

    def apply(self, cfg):
        """Write this backend's settings onto a Config dataclass instance."""
        if self.kind == "openai":
            cfg.backend = "openai"
            cfg.hive_base_url = self.base_url
            cfg.hive_api_key = self.resolve_key()
            cfg.hive_writer_model = self.models["executor"]
            cfg.hive_verifier_model = self.models["verifier"]
            cfg.hive_compressor_model = self.models["compressor"]
        elif self.kind == "ollama":
            cfg.backend = "ollama"
            cfg.ollama_url = self.base_url
            cfg.planner_model = self.models["planner"]
            cfg.executor_model = self.models["executor"]
            cfg.verifier_model = self.models["verifier"]
            cfg.compressor_model = self.models["compressor"]
        elif self.kind == "fake":
            # a scripted model cannot answer council/verifier calls — turn them off
            cfg.reasoning_depth = 0
        cfg.model_timeout_sec = int(self.timeout)
        return cfg

    def build_router(self, cfg) -> Router:
        return Router(cfg, self.build_client())
