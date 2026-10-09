from __future__ import annotations

import tempfile
from pathlib import Path

from drift.extract_docs import extract_claims_from_files, scan_file
from drift.models import Claim


def test_extract_npm_scripts():
    content = """# README

Run the dev server:

```bash
npm run dev
```

Or use pnpm:

```
pnpm run build
```

And yarn:

    yarn test

Also bun:

~ bun start ~
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content)
        path = Path(f.name)

    claims = list(scan_file(path))
    path.unlink()

    npm_claims = [c for c in claims if c.kind == "npm_script"]
    assert len(npm_claims) == 4
    texts = {c.text for c in npm_claims}
    assert "npm run dev" in texts
    assert "pnpm run build" in texts
    assert "yarn test" in texts
    assert "bun start" in texts


def test_extract_env_vars():
    content = """# Config

Set your API key:

```bash
export API_KEY=secret123
```

Or in .env:

```
DATABASE_URL=postgres://localhost:5432/db
YOUR_API_KEY=placeholder
<your-secret-key>=value
```
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content)
        path = Path(f.name)

    claims = list(scan_file(path))
    path.unlink()

    env_claims = [c for c in claims if c.kind == "env_var"]
    texts = {c.text for c in env_claims}
    assert "API_KEY=secret123" in texts
    assert "DATABASE_URL=postgres://localhost:5432/db" in texts
    assert "YOUR_API_KEY=placeholder" in texts


def test_extract_ports():
    content = """# Server

Run on localhost:3000

```bash
PORT=8080 npm start
```

The port 3001 is default.
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content)
        path = Path(f.name)

    claims = list(scan_file(path))
    path.unlink()

    port_claims = [c for c in claims if c.kind == "port"]
    texts = {c.text for c in port_claims}
    assert "localhost:3000" in texts
    assert "PORT=8080" in texts or "8080" in texts
    assert "port 3001" in texts


def test_extract_node_version():
    content = """# Requirements

Node >=18.0.0 required.

Also works with node 16.14.0

But not node 14.x
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content)
        path = Path(f.name)

    claims = list(scan_file(path))
    path.unlink()

    engine_claims = [c for c in claims if c.kind == "engine"]
    texts = {c.text for c in engine_claims}
    assert any("18" in t for t in texts)
    assert any("16.14.0" in t for t in texts)
    # Check no major version 14
    majors = {int(t.split()[1].split(".")[0]) for t in texts if t.startswith("node ")}
    assert 14 not in majors


def test_extract_routes():
    content = """# API

## Endpoints

GET /api/users

```bash
curl -X POST /api/items
```

```js
fetch('/api/data')
```

And `/api/health` in text.
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content)
        path = Path(f.name)

    claims = list(scan_file(path))
    path.unlink()

    route_claims = [c for c in claims if c.kind == "route"]
    texts = {c.text for c in route_claims}
    assert "GET /api/users" in texts
    assert "curl POST /api/items" in texts
    assert "fetch('/api/data')" in texts
    assert "/api/health" in texts


def test_placeholders_and_help():
    content = """# CLI

```bash
npm run deploy -- --help
```

Set YOUR_API_KEY in .env

```
<your-token>=abc
```
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content)
        path = Path(f.name)

    claims = list(scan_file(path))
    path.unlink()

    npm_claims = [c for c in claims if c.kind == "npm_script"]
    assert len(npm_claims) == 1
    assert "npm run deploy" in npm_claims[0].text

    env_claims = [c for c in claims if c.kind == "env_var"]
    texts = {c.text for c in env_claims}
    assert "YOUR_API_KEY=" in texts or "YOUR_API_KEY" in str(texts)


def test_context_capture():
    content = """# Introduction

This is a paragraph with some context about the project.
It spans multiple lines and should be captured.

```bash
npm run build
```

Another paragraph after the code block.
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content)
        path = Path(f.name)

    claims = list(scan_file(path))
    path.unlink()

    npm_claims = [c for c in claims if c.kind == "npm_script"]
    assert len(npm_claims) == 1
    assert "context about the project" in npm_claims[0].context
    assert len(npm_claims[0].context) <= 400


def test_fenced_block_tracking():
    content = """```bash
npm run inside-fence
```

npm run outside-fence

```js
console.log('hello')
```
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content)
        path = Path(f.name)

    claims = list(scan_file(path))
    path.unlink()

    npm_claims = [c for c in claims if c.kind == "npm_script"]
    assert len(npm_claims) == 2
    sources = {c.source for c in npm_claims}
    assert sources == {"text"}


def test_localhost_alone_not_extracted():
    content = """# Server

Just localhost without port.
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content)
        path = Path(f.name)

    claims = list(scan_file(path))
    path.unlink()

    port_claims = [c for c in claims if c.kind == "port"]
    assert len(port_claims) == 0


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])