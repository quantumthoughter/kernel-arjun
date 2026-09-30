import importlib.util
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from arjun.memory import EngramMemory
from arjun.models import FakeModel
from arjun.verifier import parse_json_block

MISSION = Path(__file__).parent.parent / "missions" / "kala-chakra"


def _load_checker():
    spec = importlib.util.spec_from_file_location("check_canon", MISSION / "check_canon.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_render_seed_shape():
    from arjun.cli import render_seed

    s = {
        "id": "10", "file": "book/10_palace_722.md", "title": "The Palace of 722",
        "words": 3000, "ground": "722 deities", "path": "poetic", "fruit": "file ≥3000",
        "query": "make 722 inevitable", "boundary": True,
    }
    text = render_seed(s)
    assert "book/10_palace_722.md" in text
    assert "minimum 3000 words" in text
    assert "722 deities" in text


def test_checker_passes_on_run1():
    checker = _load_checker()
    book = MISSION / "run1" / "book"
    assert book.exists(), "run1 book missing"
    canon = (MISSION / "run1" / "canon.md").read_text()
    reg = {Path(k).name: v for k, v in checker.parse_register(canon).items()}
    assert reg["21_wheel_turns.md"] == 3000
    total = 0
    for f in sorted(book.glob("*.md")):
        wc = checker.word_count(f.read_text())
        total += wc
        assert wc >= reg[f.name], f"{f.name} short: {wc}"
    assert total >= 50000
    assert total == 91269


def test_parse_json_block_plain():
    assert parse_json_block('{"kind": "think"}') == {"kind": "think"}


def test_parse_json_block_fenced():
    text = '```json\n{"pass": true, "reason": "ok"}\n```'
    assert parse_json_block(text)["pass"] is True


def test_parse_json_block_embedded():
    text = 'here is the answer: {"kind": "tool", "tool": "shell", "args": {"cmd": "ls"}} done'
    assert parse_json_block(text)["tool"] == "shell"


def test_memory_roundtrip(tmp_path):
    fake = FakeModel()
    mem = EngramMemory(str(tmp_path / "engrams.json"), lambda t: fake.embed("x", t), top_k=3)
    assert mem.store("the sky is blue", importance=0.9) is not None
    assert mem.store("water is wet", importance=0.3) is not None
    hits = mem.recall("sky", k=1)
    assert hits and "sky" in hits[0]["content"]
    stats = mem.stats()
    assert stats["total"] == 2


def test_dry_run_end_to_end(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "arjun.cli",
            "--config",
            str(tmp_path / "nonexistent.yaml"),
            "start",
            "Dry run goal",
            "--dod",
            "hello.txt written",
            "--workspace",
            str(workspace),
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        timeout=300,
        cwd=str(Path(__file__).parent.parent),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (workspace / "hello.txt").exists()
    assert "Jai Arjun" in (workspace / "hello.txt").read_text()


def test_sdk_end_to_end(tmp_path):
    """The SDK embeds the kernel: goal -> run -> verified done."""
    from arjun.sdk import Arjun, Backend, word_count_gate

    script = [
        json.dumps({"tasks": [{"title": "Write hi", "detail": "create hi.txt"}]}),
        json.dumps({"kind": "tool", "tool": "write_file",
                    "args": {"path": "hi.txt", "content": "Jai Arjun\n"}, "note": "write"}),
        json.dumps({"kind": "finish", "note": "done", "evidence": ["wrote hi.txt"]}),
    ]
    ws = tmp_path / "sdkws"
    k = Arjun(
        workspace=str(ws),
        backend=Backend(kind="fake", script=script),
        dsn="host=127.0.0.1 port=5432 dbname=arjun user=quan_yin",
        verifier=word_count_gate("hi.txt", 1),
        verbose=False,
    )
    g = k.goal("SDK test", dod="hi.txt written", max_tokens=20000)
    res = k.run(g)
    assert res.status == "done"
    assert res.meter.tasks_done == 1
    assert (ws / "hi.txt").exists()


def test_sdk_context_anatomy():
    from arjun.sdk.verifiers import DeterministicVerifier

    assert DeterministicVerifier(lambda g, t, s, a: (True, "ok")).verify({}, {}, [], [])["pass"]


def test_vak_roundtrip(tmp_path):
    from arjun.vak import Vault

    v = Vault(name="test-vault")
    v.set_identity({"agent": "Æmma Hø", "owner": "Quantum Thoughter"})
    v.add_engram("memory is pure text", importance=0.9, tags=["law"])
    p = tmp_path / "mind.vak"
    v.write(p)

    v2 = Vault.read(p)
    assert v2.name == "test-vault"
    assert len(v2.engrams) == 1
    assert v2.engrams[0].content == "memory is pure text"
    assert v2.seal is not None


def test_vak_tamper_detection(tmp_path):
    import pytest
    from arjun.vak import Vault

    v = Vault()
    v.add_engram("original truth", importance=0.8)
    p = tmp_path / "mind.vak"
    v.write(p)
    raw = p.read_text()
    with pytest.raises(ValueError):
        Vault.from_text(raw.replace("original truth", "altered lie"))


def test_vak_is_universal_text(tmp_path):
    from arjun.vak import Vault, SIGNATURE

    v = Vault()
    v.add_engram("readable by any system", tags=["a", "b"])
    text = v.to_text()
    assert text.startswith(SIGNATURE)
    assert "readable by any system" in text          # plain UTF-8, greppable
    assert "model_agnostic=1" in text
