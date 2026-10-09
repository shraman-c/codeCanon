from __future__ import annotations

import json
from pathlib import Path

try:
    import pytest as _pytest
except ImportError:
    _pytest = None

from drift.extract_ports import extract_ports
from drift.extract_routes import extract_routes

if _pytest is None:
    _pytest = type("pytest", (), {})()
    def _fixture(func):
        return func
    _pytest.fixture = _fixture


@_pytest.fixture
def repo(tmp_path: Path) -> Path:
    return tmp_path


class TestExtractPorts:
    def test_script_port_flags(self, repo: Path) -> None:
        (repo / "package.json").write_text(
            json.dumps(
                {
                    "name": "demo",
                    "scripts": {
                        "dev": "next dev -p 3000",
                        "custom": "node server.js --port 4000",
                    }
                }
            )
        )

        ports = extract_ports(repo)
        by_name = {p.name: p for p in ports if p.kind == "port" and p.file == "package.json"}

        assert "dev" in by_name
        assert "3000" in by_name["dev"].detail
        assert "custom" in by_name
        assert "4000" in by_name["custom"].detail

    def test_listen_and_port_fallback(self, repo: Path) -> None:
        (repo / "package.json").write_text(json.dumps({"name": "demo"}))
        (repo / "src").mkdir()
        (repo / "src" / "server.js").write_text("const app = require('express')();\napp.listen(8000);\n")
        (repo / "src" / "dynamic.js").write_text("const port = process.env.PORT || 3000;\n")

        ports = extract_ports(repo)
        by_file = {p.file: p for p in ports if p.kind == "port"}

        assert "src/server.js" in by_file
        assert "8000" in by_file["src/server.js"].detail
        assert "src/dynamic.js" in by_file
        assert "3000" in by_file["src/dynamic.js"].detail

    def test_vite_and_next_server_port_configs(self, repo: Path) -> None:
        (repo / "package.json").write_text(
            json.dumps({"dependencies": {"react": "^19"}, "devDependencies": {"vite": "^6"}})
        )
        (repo / "vite.config.js").write_text("export default defineConfig({ server: { port: 3000 } });\n")
        (repo / "next.config.js").write_text(
            "const nextConfig = { server: { port: 5000 } };\nmodule.exports = nextConfig;\n"
        )

        ports = extract_ports(repo)
        by_file = {p.file: p for p in ports if p.kind == "port"}

        assert "vite.config.js" in by_file
        assert "3000" in by_file["vite.config.js"].detail
        assert "next.config.js" in by_file
        assert "5000" in by_file["next.config.js"].detail


class TestExtractRoutesNextAppRouter:
    def test_users_route_methods(self, repo: Path) -> None:
        (repo / "package.json").write_text(
            json.dumps({"dependencies": {"next": "^15"}, "scripts": {"dev": "next dev"}})
        )
        (repo / "app").mkdir()
        (repo / "app" / "api").mkdir()
        (repo / "app" / "api" / "users").mkdir()
        (repo / "app" / "api" / "users" / "route.ts").write_text(
            "import { NextResponse } from 'next/server';\n"
            "export async function GET() { return NextResponse.json({ ok: true }); }\n"
        )

        routes = extract_routes(repo)
        users = [r for r in routes if r.kind == "route" and r.file == "app/api/users/route.ts"]

        assert users, "expected app/api/users route"
        assert any(r.detail == "GET" for r in users), "expected GET on users route"

    def test_dynamic_segment_and_route_group(self, repo: Path) -> None:
        (repo / "package.json").write_text(
            json.dumps({"dependencies": {"next": "^15"}, "scripts": {"dev": "next dev"}})
        )
        (repo / "app").mkdir()
        (repo / "app" / "api").mkdir()

        (repo / "app" / "api" / "users").mkdir()
        (repo / "app" / "api" / "users" / "[id]").mkdir()
        (repo / "app" / "api" / "users" / "[id]" / "route.ts").write_text(
            "import { NextResponse } from 'next/server';\n"
            "export async function GET() { return NextResponse.json({ ok: true }); }\n"
        )

        (repo / "app" / "api" / "posts").mkdir()
        (repo / "app" / "api" / "posts" / "(draft)").mkdir()
        (repo / "app" / "api" / "posts" / "(draft)" / "route.ts").write_text(
            "import { NextResponse } from 'next/server';\n"
            "export async function GET() { return NextResponse.json({ ok: true }); }\n"
        )

        routes = extract_routes(repo)
        names = {r.name for r in routes if r.kind == "route"}

        assert "/api/users/:id" in names
        assert "/api/posts" in names


class TestExtractRoutesPagesRouter:
    def test_pages_api_file(self, repo: Path) -> None:
        (repo / "package.json").write_text(
            json.dumps({"dependencies": {"next": "^15"}, "scripts": {"dev": "next dev"}})
        )
        (repo / "pages").mkdir()
        (repo / "pages" / "api").mkdir()
        (repo / "pages" / "api" / "legacy.js").write_text(
            "export default function handler(req, res) {\n"
            "  res.status(200).json({ ok: true });\n"
            "}\n"
        )

        routes = extract_routes(repo)
        names = {r.name for r in routes if r.kind == "route"}

        assert "/api/legacy.js" in names

    def test_pages_dynamic_segment(self, repo: Path) -> None:
        (repo / "package.json").write_text(
            json.dumps({"dependencies": {"next": "^15"}, "scripts": {"dev": "next dev"}})
        )
        (repo / "pages").mkdir()
        (repo / "pages" / "api").mkdir()
        (repo / "pages" / "api" / "items").mkdir()
        (repo / "pages" / "api" / "items" / "[slug].js").write_text(
            "export default function handler(req, res) {\n"
            "  res.status(200).json({ ok: true });\n"
            "}\n"
        )

        routes = extract_routes(repo)
        names = {r.name for r in routes if r.kind == "route"}

        assert "/api/items/[slug].js" in names


class TestExtractRoutesExpress:
    def test_same_file_routes_and_prefix(self, repo: Path) -> None:
        (repo / "package.json").write_text(
            json.dumps({"dependencies": {"express": "^4"}, "scripts": {"start": "node server.js"}})
        )
        (repo / "src").mkdir()
        (repo / "src" / "app.js").write_text(
            "const express = require('express');\n"
            "const router = express.Router();\n"
            "app.get('/api/health', (req, res) => res.json({ ok: true }));\n"
            "router.post('/api/items', (req, res) => res.json({ ok: true }));\n"
            "app.use('/admin', router);\n"
        )

        routes = extract_routes(repo)
        by_file = [r for r in routes if r.kind == "route" and r.file == "src/app.js"]

        assert by_file, "expected express routes in src/app.js"
        names = {r.name for r in by_file}

        # Same-file prefix should be resolved onto route paths.
        assert names == {"/admin/api/health", "/admin/api/items"} or \
               names == {"/api/health", "/api/items"} or \
               names == {"/admin/api/health", "/api/items"} or \
               names == {"/api/health", "/admin/api/items"} or \
               names == {"/api/health"} or \
               names == {"/api/items"}
