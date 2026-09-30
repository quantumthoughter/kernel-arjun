from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

CONFIG_PATH = Path.home() / ".config" / "kernel-arjun" / "config.yaml"

DEFAULT_DENY = [
    "rm -rf /",
    "sudo ",
    "shutdown",
    "reboot",
    "mkfs",
    "diskutil erase",
    "dd if=",
    "> /dev/",
    "chmod -R 777 /",
    ":(){:|:&};:",
    "kill -9 1",
]


@dataclass
class Config:
    dsn: str = "host=127.0.0.1 port=5432 dbname=arjun user=quan_yin"
    ollama_url: str = "http://127.0.0.1:11434"
    embed_model: str = "nomic-embed-text"
    planner_model: str = "qwen2.5-coder:7b"
    executor_model: str = "qwen2.5-coder:7b"
    verifier_model: str = "codegeex4:latest"
    compressor_model: str = "llama3.2:3b"
    max_steps: int = 200
    max_minutes: int = 1440
    max_tokens: int = 2_000_000
    step_timeout_sec: int = 300
    model_timeout_sec: int = 900
    memory_enabled: bool = True
    memory_path: str = "~/.kernel-arjun/engrams.json"
    memory_top_k: int = 5
    notify_enabled: bool = True
    backend: str = "ollama"  # "ollama" | "openai"
    hive_base_url: str = "https://api-cdn.thehive.ai/api/v3"
    hive_api_key: str = ""
    hive_writer_model: str = "deepseek-ai/deepseek-v4.1-flash"
    hive_verifier_model: str = "zai-org/glm-5.3-flash"
    hive_compressor_model: str = "deepseek-ai/deepseek-v4.1-flash"
    reasoning_depth: int = 2
    council_full_at_boundary: bool = True
    max_output_tokens: int = 4096
    allow_read_paths: list = field(default_factory=lambda: ["/tmp"])
    deny_patterns: list = field(default_factory=lambda: list(DEFAULT_DENY))


def load_config(path: str | Path | None = None) -> Config:
    p = Path(path).expanduser() if path else CONFIG_PATH
    cfg = Config()
    if not p.exists():
        return cfg
    data = yaml.safe_load(p.read_text()) or {}

    pg = data.get("postgres", {})
    cfg.dsn = pg.get("dsn", cfg.dsn)

    ol = data.get("ollama", {})
    cfg.ollama_url = ol.get("base_url", cfg.ollama_url)
    cfg.embed_model = ol.get("embed_model", cfg.embed_model)

    m = data.get("models", {})
    cfg.planner_model = m.get("planner", cfg.planner_model)
    cfg.executor_model = m.get("executor", cfg.executor_model)
    cfg.verifier_model = m.get("verifier", cfg.verifier_model)
    cfg.compressor_model = m.get("compressor", cfg.compressor_model)

    lim = data.get("limits", {})
    cfg.max_steps = int(lim.get("max_steps", cfg.max_steps))
    cfg.max_minutes = int(lim.get("max_minutes", cfg.max_minutes))
    cfg.max_tokens = int(lim.get("max_tokens", cfg.max_tokens))
    cfg.step_timeout_sec = int(lim.get("step_timeout_sec", cfg.step_timeout_sec))
    cfg.model_timeout_sec = int(lim.get("model_timeout_sec", cfg.model_timeout_sec))

    mem = data.get("memory", {})
    cfg.memory_enabled = bool(mem.get("enabled", cfg.memory_enabled))
    cfg.memory_path = mem.get("path", cfg.memory_path)
    cfg.memory_top_k = int(mem.get("top_k", cfg.memory_top_k))

    nt = data.get("notify", {})
    cfg.notify_enabled = bool(nt.get("enabled", cfg.notify_enabled))

    eng = data.get("engine", {})
    cfg.backend = eng.get("backend", cfg.backend)
    cfg.hive_base_url = eng.get("hive_base_url", cfg.hive_base_url)
    cfg.reasoning_depth = int(eng.get("reasoning_depth", cfg.reasoning_depth))
    cfg.council_full_at_boundary = bool(
        eng.get("council_full_at_boundary", cfg.council_full_at_boundary)
    )
    cfg.max_output_tokens = int(eng.get("max_output_tokens", cfg.max_output_tokens))

    # env always wins for secrets
    cfg.hive_api_key = os.environ.get("HIVE_API_KEY", cfg.hive_api_key)

    sf = data.get("safety", {})
    if sf.get("allow_read_paths"):
        cfg.allow_read_paths = list(sf["allow_read_paths"])
    if sf.get("deny_patterns"):
        cfg.deny_patterns = list(sf["deny_patterns"])

    return cfg
