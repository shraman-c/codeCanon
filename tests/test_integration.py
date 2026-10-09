from __future__ import annotations

import tempfile
from pathlib import Path

from drift.detect import detect, is_web_project
from drift.extract_pkg import extract_pkg
from drift.extract_env import extract_env
from drift.extract_routes import extract_routes
from drift.extract_ports import extract_ports
from drift.extract_docs import scan_file, extract_claims_from_files
from drift.extract_images import collect_image_claims, extract_image_claims
from drift.match import match_claims, apply_image_discount
from drift.models import Claim, Fact, Finding
from drift.report import write_report
from drift.judge import judge, reset_stats
from drift.patch import patch as make_patches, combined_patch


def _write_temp_file(content: str, suffix: str = ".md") -> Path:
    with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False) as f:
        f.write(content)
        return Path(f.name)


def test_full_pipeline_next_app():
    """Test the complete pipeline on the next_app fixture."""
    repo = Path("benchmark/fixtures/next_app")
    assert repo.exists(), "Fixture not found"

    # 1. Detect
    assert is_web_project(repo)
    kind = detect(repo)
    assert kind == "next_app"

    # 2. Extract facts
    pkg_facts = extract_pkg(repo)
    env_facts = extract_env(repo)
    route_facts = extract_routes(repo)
    port_facts = extract_ports(repo)
    facts = pkg_facts + env_facts + route_facts + port_facts
    assert len(facts) > 0

    # 3. Extract text claims
    doc_files = list(repo.rglob("*.md")) + list(repo.rglob("*.mdx"))
    claims = extract_claims_from_files(doc_files)
    assert len(claims) > 0

    # 4. Match
    findings = match_claims(claims, facts)
    assert len(findings) == len(claims)
    statuses = {f.status for f in findings}
    assert "OK" in statuses or "STALE" in statuses or "SUSPECT" in statuses

    # 5. Image claims (should work without images)
    image_claims = list(collect_image_claims(repo, doc_files))
    assert isinstance(image_claims, list)

    # 6. Apply image discount
    findings_with_discount = apply_image_discount(findings)
    assert len(findings_with_discount) == len(findings)

    # 7. Report
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "drift-report.json"
        model_info = {"id": "test-model", "mode": "api", "config": {"threshold": 0.6}}
        write_report(
            repo_path=str(repo),
            kind=kind,
            mode="scan",
            facts=facts,
            claims=claims,
            findings=findings_with_discount,
            model=model_info,
            output=out,
            files_read=len(doc_files),
            images_read=0,
        )
        assert out.exists()
        import json
        data = json.loads(out.read_text())
        assert "metadata" in data
        assert "findings" in data
        assert data["metadata"]["kind"] == "next_app"

    # 8. Judge (requires LLM, so we test the function exists and handles no-op)
    reset_stats()
    findings_post_judge = judge(findings_with_discount)  # will skip if no LLM
    assert len(findings_post_judge) == len(findings_with_discount)

    # 9. Patch
    findings_with_patch = make_patches(findings_post_judge, repo=repo)
    assert len(findings_with_patch) == len(findings_post_judge)

    combined = combined_patch(findings_with_patch, repo=repo)
    assert combined is None or isinstance(combined, str)


def test_extract_docs_various_formats():
    """Test extract_docs handles various markdown formats."""
    content = """# Title

## npm scripts

Run `npm run dev` or `pnpm build`.

```bash
yarn test
```

## env vars

Set DATABASE_URL=postgres://localhost/db and YOUR_TOKEN=xxx.

## ports

Server runs on localhost:3000 or PORT=8080.

## routes

GET /api/users
POST /api/items
curl -X PUT /api/data
fetch('/api/health')

## node version

Requires node >=18.0.0
"""
    path = _write_temp_file(content)
    try:
        claims = list(scan_file(path))
        kinds = {c.kind for c in claims}
        assert "npm_script" in kinds
        assert "env_var" in kinds
        assert "port" in kinds
        assert "route" in kinds
        assert "engine" in kinds

        npm = [c for c in claims if c.kind == "npm_script"]
        assert any("dev" in c.text for c in npm)
        assert any("build" in c.text for c in npm)
        assert any("test" in c.text for c in npm)

        env = [c for c in claims if c.kind == "env_var"]
        assert any("DATABASE_URL" in c.text for c in env)

        ports = [c for c in claims if c.kind == "port"]
        assert any("3000" in c.text for c in ports)
        assert any("8080" in c.text for c in ports)

        routes = [c for c in claims if c.kind == "route"]
        route_texts = {c.text for c in routes}
        assert "GET /api/users" in route_texts
        assert "POST /api/items" in route_texts
        assert any("curl" in t for t in route_texts)
        assert any("fetch" in t for t in route_texts)

        engines = [c for c in claims if c.kind == "engine"]
        assert any("18" in c.text for c in engines)
    finally:
        path.unlink()


def test_match_all_kinds():
    """Test matcher handles all claim kinds."""
    claims = [
        Claim("npm_script", "npm run dev", "README.md", 1, "ctx", "text"),
        Claim("npm_script", "npm run missing", "README.md", 2, "ctx", "text"),
        Claim("env_var", "DATABASE_URL=postgres://...", "README.md", 3, "ctx", "text"),
        Claim("env_var", "MISSING_VAR=secret123", "README.md", 4, "ctx", "text"),
        Claim("port", "localhost:3000", "README.md", 5, "ctx", "text"),
        Claim("port", "port 9999", "README.md", 6, "ctx", "text"),
        Claim("engine", "node 20.0.0", "README.md", 7, "ctx", "text"),
        Claim("engine", "node 14.0.0", "README.md", 8, "ctx", "text"),
        Claim("route", "GET /api/users", "README.md", 9, "ctx", "text"),
        Claim("route", "GET /api/missing", "README.md", 10, "ctx", "text"),
        Claim("dependency", "react", "README.md", 11, "ctx", "text"),
        Claim("dependency", "missing-pkg", "README.md", 12, "ctx", "text"),
    ]

    facts = [
        Fact("npm_script", "dev", "next dev", "package.json", 1),
        Fact("env_var", "DATABASE_URL", "server-side", ".env.example", 1),
        Fact("port", "3000", "listen(3000)", "server.js", 1),
        Fact("engine", "node", ">=18", "package.json", 1),
        Fact("route", "/api/users", "GET,POST", "app/api/users/route.ts", 1),
        Fact("dependency", "react", "^18", "package.json", 1),
    ]

    findings = match_claims(claims, facts)
    assert len(findings) == 12

    # Check expected statuses
    status_map = {f.claim.text: f.status for f in findings}
    assert status_map["npm run dev"] == "OK"
    assert status_map["npm run missing"] == "STALE"
    assert status_map["DATABASE_URL=postgres://..."] == "OK"
    assert status_map["MISSING_VAR=secret123"] == "STALE"
    assert status_map["localhost:3000"] == "OK"
    assert status_map["port 9999"] == "STALE"
    assert status_map["node 20.0.0"] == "OK"
    assert status_map["node 14.0.0"] == "STALE"
    assert status_map["GET /api/users"] == "OK"
    assert status_map["GET /api/missing"] == "STALE"
    assert status_map["react"] == "OK"
    assert status_map["missing-pkg"] == "STALE"


def test_image_discount():
    """Test image confidence discount logic."""
    claim_stale = Claim("npm_script", "npm run old", "README.md", 1, "ctx", "image", extracted_text="$ npm run old")
    claim_stale_long = Claim("npm_script", "npm run old", "README.md", 1, "ctx", "image", extracted_text="$ npm run old\nready on http://localhost:3000\nserver started")
    claim_ok = Claim("npm_script", "npm run dev", "README.md", 1, "ctx", "image", extracted_text="$ npm run dev")
    claim_suspect = Claim("npm_script", "npm run dev:local", "README.md", 1, "ctx", "image", extracted_text="$ npm run dev:local")

    fact = Fact("npm_script", "dev", "next dev", "package.json", 1)

    findings = match_claims([claim_stale, claim_stale_long, claim_ok, claim_suspect], [fact])
    findings = apply_image_discount(findings)

    status_map = {f.claim.extracted_text: f.status for f in findings}
    assert status_map["$ npm run old"] == "SUSPECT"  # short quote, downgraded
    assert status_map["$ npm run old\nready on http://localhost:3000\nserver started"] == "STALE"  # long quote, stays STALE
    assert status_map["$ npm run dev"] == "OK"
    assert status_map["$ npm run dev:local"] == "SUSPECT"


def test_cli_scan_help():
    """Test CLI help works."""
    import subprocess
    repo_root = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        ["python", "scripts/drift.py", "scan", "--help"],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    assert result.returncode == 0
    assert "scan" in result.stdout
    assert "--no-llm" in result.stdout
    assert "--no-images" in result.stdout


def test_non_web_repo_rejected():
    """Test non-web repos are rejected."""
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        (repo / "README.md").write_text("# Not a web project\n")
        assert not is_web_project(repo)


def test_extract_images_stub():
    """Test extract_images returns empty list when vision not available."""
    # Uses the stub vision.py which returns []
    repo = Path("benchmark/fixtures/next_app")
    doc_files = list(repo.rglob("*.md"))
    claims = list(collect_image_claims(repo, doc_files))
    # Should be empty because vision.extract_claims returns []
    assert claims == []


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])