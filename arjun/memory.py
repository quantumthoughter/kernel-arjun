from __future__ import annotations

import json
import math
import os
import tempfile
import time
import uuid
from pathlib import Path


class EngramMemory:
    """Shared-schema engram store: JSON file + Ollama embeddings.

    Mirrors the emma-context-engine format so memory can be shared or standalone.
    """

    def __init__(self, path: str, embedder, enabled: bool = True, top_k: int = 5):
        self.path = Path(os.path.expanduser(path))
        self.embedder = embedder
        self.enabled = enabled
        self.top_k = top_k
        self.engrams: list[dict] = []
        self._mtime = 0.0
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self.engrams = json.loads(self.path.read_text())
                self._mtime = self.path.stat().st_mtime
                return
            except Exception:
                pass
        self.engrams = []

    def _reload_if_changed(self) -> None:
        try:
            if self.path.exists() and self.path.stat().st_mtime > self._mtime:
                self._load()
        except OSError:
            pass

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), prefix=".engrams-")
        with os.fdopen(fd, "w") as f:
            json.dump(self.engrams, f, indent=2)
        os.replace(tmp, self.path)
        self._mtime = self.path.stat().st_mtime

    @staticmethod
    def _cos(a: list[float], b: list[float]) -> float:
        if not a or not b:
            return 0.0
        n = min(len(a), len(b))
        dot = sum(a[i] * b[i] for i in range(n))
        na = math.sqrt(sum(x * x for x in a[:n]))
        nb = math.sqrt(sum(x * x for x in b[:n]))
        return dot / (na * nb) if na and nb else 0.0

    def store(self, content: str, importance: float = 0.5, tags: list[str] | None = None) -> str | None:
        if not self.enabled or not content.strip():
            return None
        try:
            emb = self.embedder(content)
        except Exception:
            return None
        self._reload_if_changed()
        rec = {
            "id": str(uuid.uuid4()),
            "content": content,
            "embedding": emb,
            "importance": float(importance),
            "strength": 1.0,
            "tags": tags or [],
            "accessCount": 0,
            "createdAt": time.time(),
            "lastAccessed": time.time(),
        }
        self.engrams.append(rec)
        self._save()
        return rec["id"]

    def recall(self, query: str, k: int | None = None) -> list[dict]:
        if not self.enabled or not self.engrams:
            return []
        k = k or self.top_k
        try:
            q = self.embedder(query)
        except Exception:
            return []
        self._reload_if_changed()
        scored = []
        for e in self.engrams:
            sim = self._cos(q, e.get("embedding", []))
            scored.append((sim * e.get("strength", 1.0) * e.get("importance", 0.5), e))
        scored.sort(key=lambda x: -x[0])
        out = []
        for score, e in scored[:k]:
            if score <= 0:
                continue
            e["accessCount"] = e.get("accessCount", 0) + 1
            e["lastAccessed"] = time.time()
            out.append(
                {"content": e["content"], "score": round(score, 4), "tags": e.get("tags", [])}
            )
        if out:
            self._save()
        return out

    def decay(self, rate: float = 0.05) -> None:
        for e in self.engrams:
            e["strength"] = max(0.05, e.get("strength", 1.0) * (1 - rate))
        self._save()

    def stats(self) -> dict:
        n = len(self.engrams)
        avg = sum(e.get("strength", 1.0) for e in self.engrams) / n if n else 0.0
        return {"total": n, "avg_strength": round(avg, 3), "path": str(self.path)}
