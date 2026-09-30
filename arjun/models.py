from __future__ import annotations

import json
from dataclasses import dataclass

import httpx


class ModelError(Exception):
    pass


@dataclass
class ModelResponse:
    content: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    reasoning: str = ""
    reasoning_tokens: int = 0


class OpenAIClient:
    """OpenAI-compatible chat client (Hive, DeepSeek, vLLM, LM Studio, ...).

    Captures the assistant's answer *and* its reasoning trace so the engine can
    preserve the model's internal deliberation instead of discarding it.
    """

    def __init__(self, base_url: str, api_key: str = "", timeout: float = 300.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.client = httpx.Client(
            timeout=httpx.Timeout(timeout, connect=20.0, read=timeout),
            limits=httpx.Limits(max_connections=8, max_keepalive_connections=4),
        )

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def chat(
        self,
        model: str,
        messages: list[dict],
        json_mode: bool = True,
        temperature: float = 0.6,
        num_ctx: int = 16384,
        max_tokens: int = 4096,
    ) -> ModelResponse:
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        import time

        last: Exception | None = None
        for attempt in range(3):
            try:
                r = self.client.post(
                    f"{self.base_url}/chat/completions", json=payload, headers=self._headers()
                )
                if r.status_code in (429, 500, 502, 503, 504):
                    raise httpx.HTTPStatusError(
                        f"retryable {r.status_code}", request=r.request, response=r
                    )
                r.raise_for_status()
                data = r.json()
                break
            except httpx.HTTPStatusError as e:
                last = e
                code = e.response.status_code if e.response is not None else 0
                if code not in (429, 500, 502, 503, 504):
                    raise ModelError(f"openai chat failed: {e}") from e
                time.sleep(2 * (attempt + 1))
            except httpx.HTTPError as e:
                last = e
                time.sleep(2 * (attempt + 1))
        else:
            raise ModelError(f"openai chat failed after retries: {last}")
        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        usage = data.get("usage") or {}
        details = usage.get("completion_tokens_details") or {}
        return ModelResponse(
            content=msg.get("content") or "",
            model=data.get("model", model),
            tokens_in=int(usage.get("prompt_tokens", 0) or 0),
            tokens_out=int(usage.get("completion_tokens", 0) or 0),
            reasoning=msg.get("reasoning_content") or "",
            reasoning_tokens=int(details.get("reasoning_tokens", 0) or 0),
        )

    def embed(self, model: str, text: str) -> list[float]:
        try:
            r = self.client.post(
                f"{self.base_url}/embeddings",
                json={"model": model, "input": text},
                headers=self._headers(),
                timeout=120.0,
            )
            r.raise_for_status()
            return r.json()["data"][0]["embedding"]
        except httpx.HTTPError as e:
            raise ModelError(f"openai embed failed: {e}") from e

    def models(self) -> list[str]:
        r = self.client.get(f"{self.base_url}/models", headers=self._headers(), timeout=30.0)
        r.raise_for_status()
        return [m["id"] for m in r.json().get("data", [])]


class OllamaClient:
    def __init__(self, base_url: str, timeout: float = 900.0):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(timeout=timeout)

    def chat(
        self,
        model: str,
        messages: list[dict],
        json_mode: bool = True,
        temperature: float = 0.2,
        num_ctx: int = 16384,
        max_tokens: int | None = None,
    ) -> ModelResponse:
        opts = {"temperature": temperature, "num_ctx": num_ctx}
        if max_tokens:
            opts["num_predict"] = max_tokens
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": opts,
        }
        if json_mode:
            payload["format"] = "json"
        try:
            r = self.client.post(f"{self.base_url}/api/chat", json=payload)
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise ModelError(f"ollama chat failed: {e}") from e
        data = r.json()
        return ModelResponse(
            content=data.get("message", {}).get("content", ""),
            model=model,
            tokens_in=int(data.get("prompt_eval_count", 0) or 0),
            tokens_out=int(data.get("eval_count", 0) or 0),
        )

    def embed(self, model: str, text: str) -> list[float]:
        try:
            r = self.client.post(
                f"{self.base_url}/api/embed", json={"model": model, "input": text}, timeout=120.0
            )
            r.raise_for_status()
            return r.json()["embeddings"][0]
        except httpx.HTTPError as e:
            raise ModelError(f"ollama embed failed: {e}") from e

    def models(self) -> list[str]:
        r = self.client.get(f"{self.base_url}/api/tags", timeout=30.0)
        r.raise_for_status()
        return [m["name"] for m in r.json().get("models", [])]


class FakeModel:
    """Scripted model for dry runs. Pops replies in order; exhausted -> escalate."""

    def __init__(self, script: list[str] | None = None):
        self.script = list(script or [])
        self.calls: list[str] = []

    def chat(self, model: str, messages: list[dict], json_mode: bool = True, **kw) -> ModelResponse:
        self.calls.append(model)
        if self.script:
            content = self.script.pop(0)
        else:
            content = json.dumps({"kind": "escalate", "question": "dry-run script exhausted"})
        return ModelResponse(content=content, model=model, tokens_in=10, tokens_out=10)

    def embed(self, model: str, text: str) -> list[float]:
        vec = [0.0] * 16
        for i, ch in enumerate(text[:64]):
            vec[i % 16] += (ord(ch) % 31) / 31.0
        norm = sum(v * v for v in vec) ** 0.5 or 1.0
        return [v / norm for v in vec]


class Router:
    def __init__(self, cfg, client: OllamaClient | FakeModel):
        self.cfg = cfg
        self.client = client

    def model_for(self, role: str) -> str:
        if getattr(self.cfg, "backend", "ollama") == "openai":
            return {
                "planner": self.cfg.hive_writer_model,
                "executor": self.cfg.hive_writer_model,
                "verifier": self.cfg.hive_verifier_model,
                "compressor": self.cfg.hive_compressor_model,
            }.get(role, self.cfg.hive_writer_model)
        return {
            "planner": self.cfg.planner_model,
            "executor": self.cfg.executor_model,
            "verifier": self.cfg.verifier_model,
            "compressor": self.cfg.compressor_model,
        }.get(role, self.cfg.executor_model)

    def complete(self, role: str, messages: list[dict], json_mode: bool = True, **kw) -> ModelResponse:
        model = self.model_for(role)
        return self.client.chat(model, messages, json_mode=json_mode, **kw)
