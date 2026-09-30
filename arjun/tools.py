from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path

TOOL_NAMES = [
    "shell",
    "read_file",
    "write_file",
    "list_dir",
    "search",
    "memory_store",
    "memory_recall",
]

SENSITIVE_READ = [
    ".ssh",
    ".aws",
    ".gnupg",
    "Library/Keychains",
    ".env",
    "id_rsa",
    "id_ed25519",
    "credentials",
    "auth.json",
]


class ToolRuntime:
    def __init__(self, workspace: str, memory, cfg):
        self.workspace = Path(workspace).expanduser().resolve()
        self.memory = memory
        self.cfg = cfg
        self.workspace.mkdir(parents=True, exist_ok=True)

    def _resolve_in_workspace(self, path: str) -> Path:
        p = Path(path).expanduser()
        if not p.is_absolute():
            p = self.workspace / p
        p = p.resolve()
        if not str(p).startswith(str(self.workspace)):
            raise PermissionError(f"path outside workspace: {p}")
        return p

    def _allowed_read(self, path: str) -> Path:
        p = Path(path).expanduser()
        if not p.is_absolute():
            p = self.workspace / p
        p = p.resolve()
        s = str(p)
        if s.startswith(str(self.workspace)):
            return p
        for allowed in self.cfg.allow_read_paths:
            if s.startswith(str(Path(allowed).expanduser().resolve())):
                return p
        raise PermissionError(f"read outside workspace not allowed: {p}")

    @staticmethod
    def _is_sensitive(path: Path) -> bool:
        s = str(path)
        return any(token in s for token in SENSITIVE_READ)

    def run(self, name: str, args: dict) -> dict:
        fn = getattr(self, f"_tool_{name}", None)
        if fn is None:
            return {"ok": False, "error": f"unknown tool: {name}"}
        try:
            return fn(args or {})
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    # ---- tools ----

    def _tool_shell(self, args: dict) -> dict:
        cmd = str(args.get("cmd", "")).strip()
        if not cmd:
            return {"ok": False, "error": "empty command"}
        for pattern in self.cfg.deny_patterns:
            if pattern in cmd:
                return {"ok": False, "error": f"blocked by safety pattern: {pattern!r}"}
        try:
            proc = subprocess.run(
                cmd,
                shell=True,
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                timeout=self.cfg.step_timeout_sec,
            )
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": f"timeout after {self.cfg.step_timeout_sec}s"}
        out = (proc.stdout or "") + (("\n[stderr]\n" + proc.stderr) if proc.stderr else "")
        out = out.strip()
        truncated = len(out) > 8000
        return {
            "ok": proc.returncode == 0,
            "exit_code": proc.returncode,
            "output": out[:8000],
            "truncated": truncated,
            "summary": out[:300],
        }

    def _tool_read_file(self, args: dict) -> dict:
        p = self._allowed_read(str(args.get("path", "")))
        if self._is_sensitive(p):
            return {"ok": False, "error": "sensitive file blocked"}
        if not p.exists():
            return {"ok": False, "error": f"no such file: {p}"}
        max_bytes = int(args.get("max_bytes", 20000))
        data = p.read_bytes()[:max_bytes]
        try:
            text = data.decode("utf-8", errors="replace")
        except Exception as e:
            return {"ok": False, "error": f"decode failed: {e}"}
        return {"ok": True, "output": text, "path": str(p), "bytes": len(data), "summary": text[:300]}

    def _tool_write_file(self, args: dict) -> dict:
        p = self._resolve_in_workspace(str(args.get("path", "")))
        content = str(args.get("content", ""))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        sha = hashlib.sha256(content.encode()).hexdigest()[:16]
        return {
            "ok": True,
            "path": str(p),
            "bytes": len(content),
            "sha256": sha,
            "artifact": {"path": str(p), "sha256": sha, "kind": "file"},
            "summary": f"wrote {p.name} ({len(content)} bytes)",
        }

    def _tool_list_dir(self, args: dict) -> dict:
        p = self._allowed_read(str(args.get("path", ".")))
        if not p.is_dir():
            return {"ok": False, "error": f"not a directory: {p}"}
        entries = sorted(os.listdir(p))[:200]
        return {"ok": True, "output": "\n".join(entries), "path": str(p), "summary": f"{len(entries)} entries"}

    def _tool_search(self, args: dict) -> dict:
        pattern = str(args.get("pattern", ""))
        if not pattern:
            return {"ok": False, "error": "empty pattern"}
        root = self._allowed_read(str(args.get("path", ".")))
        max_results = int(args.get("max_results", 50))
        rx = re.compile(pattern)
        hits = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules", "__pycache__", ".venv")]
            for fname in filenames:
                fp = Path(dirpath) / fname
                if fp.stat().st_size > 2_000_000:
                    continue
                try:
                    for i, line in enumerate(fp.read_text(errors="ignore").splitlines(), 1):
                        if rx.search(line):
                            hits.append(f"{fp}:{i}: {line.strip()[:160]}")
                            if len(hits) >= max_results:
                                break
                except OSError:
                    continue
                if len(hits) >= max_results:
                    break
            if len(hits) >= max_results:
                break
        return {
            "ok": True,
            "output": "\n".join(hits) or "(no matches)",
            "summary": f"{len(hits)} matches",
        }

    def _tool_memory_store(self, args: dict) -> dict:
        eid = self.memory.store(
            str(args.get("content", "")),
            float(args.get("importance", 0.5)),
            list(args.get("tags", [])),
        )
        if eid is None:
            return {"ok": False, "error": "memory store unavailable"}
        return {"ok": True, "id": eid, "summary": "stored engram"}

    def _tool_memory_recall(self, args: dict) -> dict:
        hits = self.memory.recall(str(args.get("query", "")), int(args.get("k", self.cfg.memory_top_k)))
        return {"ok": True, "output": hits, "summary": f"{len(hits)} recalled"}
