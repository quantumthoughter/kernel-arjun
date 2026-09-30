# Publishing Kernel-Arjun to PyPI

The package name **`kernel-arjun` is free** (checked: PyPI returns 404). Here is
the whole path from this repo to `pip install kernel-arjun`.

## 0. One-time setup

```bash
cd ~/Development/Kernel-Arjun
.venv/bin/pip install build twine
```

Create accounts:
- **TestPyPI**: https://test.pypi.org/account/register/
- **PyPI**: https://pypi.org/account/register/
- Create an **API token** on each (Account → API tokens), scope "Entire account".

Store the token (better than typing it):
```bash
# ~/.pypirc
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-XXXXXXXXXXXXXXXX

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-YYYYYYYYYYYYYYYY
```

## 1. Build

```bash
cd ~/Development/Kernel-Arjun
rm -rf dist build
.venv/bin/python -m build
# → dist/kernel_arjun-0.2.0.tar.gz
# → dist/kernel_arjun-0.2.0-py3-none-any.whl
```

## 2. Verify locally (do this every time)

```bash
python3 -m venv /tmp/verify && /tmp/verify/bin/pip install dist/*.whl
/tmp/verify/bin/arjun --version
/tmp/verify/bin/python -c "from arjun import Arjun; print('SDK ok')"
```

## 3. Upload to TestPyPI first (dry run)

```bash
.venv/bin/twine upload --repository testpypi dist/*
# then, in a clean venv:
pip install --index-url https://test.pypi.org/simple/ \
            --extra-index-url https://pypi.org/simple/ kernel-arjun
```

## 4. Upload to PyPI (the real thing)

```bash
.venv/bin/twine upload dist/*
# → https://pypi.org/project/kernel-arjun/
```

Now anyone can:
```bash
pip install kernel-arjun
pip install 'kernel-arjun[mcp]'    # + MCP server
pip install 'kernel-arjun[all]'    # + MCP + dashboard extras
```

## 5. Install from GitHub (no PyPI needed)

```bash
pip install git+https://github.com/quantumthoughter/kernel-arjun.git
```

---

## Versioning

Bump `version` in `pyproject.toml` for each release (semver):
- `0.2.0` current — SDK, MCP server, dashboard, watch daemon
- bump to `0.2.1` for fixes, `0.3.0` for features

## What ships

| Command | What it does |
|---|---|
| `arjun` | the CLI (start, book, status, meter, context, watch, resume, doctor) |
| `arjun-mcp` | MCP server for opencode / Claude Desktop |
| `arjun-dashboard` | live ledger dashboard (`--port 8788`) |

## Checklist before first public release

- [ ] `README.md` and `SDK.md` are current
- [ ] `LICENSE` file present (Apache-2.0 chosen in pyproject)
- [ ] no secrets in the repo (`.gitignore` covers config.yaml, opencode.json)
- [ ] `pytest -q` green
- [ ] version bumped
- [ ] TestPyPI install verified in a clean venv
