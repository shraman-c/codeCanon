from __future__ import annotations

import json
import tempfile
from pathlib import Path

try:
    import pytest as _pytest
except ImportError:
    _pytest = None

from drift.detect import detect, is_web_project, not_web_error
from drift.extract_pkg import extract_pkg, package_manager, iter_source_files
from drift.extract_env import extract_env

if _pytest is None:
    _pytest = type("pytest", (), {})()
    def _fixture(func):
        return func
    _pytest.fixture = _fixture


@_pytest.fixture
def repo(tmp_path: Path) -> Path:
    return tmp_path


class TestDetect:
    def test_non_web_without_package_json(self, repo: Path) -> None:
        assert not is_web_project(repo)
        assert detect(repo) == "other"

    def test_empty_package_json_is_non_web(self, repo: Path) -> None:
        (repo / "package.json").write_text("{}")
        assert not is_web_project(repo)
        assert detect(repo) == "other"

    def test_next_app(self, repo: Path) -> None:
        (repo / "package.json").write_text(
            json.dumps({"dependencies": {"next": "^15"}, "scripts": {"dev": "next dev"}})
        )
        assert detect(repo) == "next_app"
        assert is_web_project(repo)

    def test_express_api(self, repo: Path) -> None:
        (repo / "package.json").write_text(
            json.dumps({"dependencies": {"express": "^4"}, "scripts": {"start": "node server.js"}})
        )
        assert detect(repo) == "express_api"
        assert is_web_project(repo)

    def test_vite_react_with_vite_signal(self, repo: Path) -> None:
        (repo / "package.json").write_text(
            json.dumps(
                {
                    "dependencies": {"react": "^19"},
                    "devDependencies": {"vite": "^6"},
                }
            )
        )
        assert detect(repo) == "vite_react"
        assert is_web_project(repo)

    def test_react_only_is_vite_react(self, repo: Path) -> None:
        (repo / "package.json").write_text(
            json.dumps({"dependencies": {"react": "^19"}})
        )
        assert detect(repo) == "vite_react"
        assert is_web_project(repo)

    def test_lockfile_based_package_manager(self, repo: Path) -> None:
        (repo / "package.json").write_text(json.dumps({"name": "demo"}))
        mappings = [
            ("pnpm", "pnpm-lock.yaml"),
            ("yarn", "yarn.lock"),
            ("bun", "bun.lockb"),
            ("npm", "package-lock.json"),
        ]
        for pm, lock in mappings:
            (repo / lock).write_text("")
            assert package_manager(repo) == pm
            (repo / lock).unlink()


class TestExtractPkg:
    def test_scripts_dependencies_engines_and_nvmrc(self, repo: Path) -> None:
        (repo / "package.json").write_text(
            json.dumps(
                {
                    "name": "demo",
                    "scripts": {"dev": "next dev", "build": "next build", "test": "playwright test"},
                    "dependencies": {"react": "^19", "next": "^15"},
                    "devDependencies": {"typescript": "^5"},
                    "engines": {"node": ">=20"},
                }
            )
        )
        (repo / ".nvmrc").write_text("20.10.0\n")

        facts = extract_pkg(repo)
        by_kind: dict[str, list] = {}
        for f in facts:
            by_kind.setdefault(f.kind, []).append(f)

        assert any(f.name == "dev" and f.detail == "next dev" for f in by_kind.get("npm_script", []))
        assert any(f.name == "build" for f in by_kind.get("npm_script", []))
        assert any(f.name == "react" for f in by_kind.get("dependency", []))
        assert any(f.name == "typescript" for f in by_kind.get("dependency", []))
        assert any(f.name == "node" for f in by_kind.get("engine", []))
        assert any(f.detail == "20.10.0" for f in by_kind.get("engine", []))

    def test_node_modules_are_skipped(self, repo: Path) -> None:
        (repo / "package.json").write_text(json.dumps({"name": "demo"}))
        (repo / "node_modules").mkdir()
        (repo / "node_modules" / "fake.js").write_text("process.env.X")
        srcs = list(iter_source_files(repo))
        assert not any("node_modules" in str(p) for p in srcs)


class TestExtractEnv:
    def test_env_var_facts_from_code_and_env_example(self, repo: Path) -> None:
        (repo / "src").mkdir()
        (repo / "src" / "app.js").write_text(
            """
const host = process.env.HOST;
const port = process.env["PORT"];
const api = process.env.API_URL;
const pub = process.env.NEXT_PUBLIC_API_URL;
"""
        )
        (repo / "src" / "env.ts").write_text("const v = import.meta.env.VITE_API_URL;")
        (repo / ".env.example").write_text("DATABASE_URL=\nCACHE_HOST=\nYOUR_SECRET=\n")

        facts = extract_env(repo)
        names = {f.name for f in facts}

        for expected in ["HOST", "API_URL", "NEXT_PUBLIC_API_URL", "VITE_API_URL", "DATABASE_URL", "CACHE_HOST"]:
            assert expected in names, f"missing env fact: {expected}"

        assert "PORT" not in names
        assert "YOUR_SECRET" not in names
        assert "NODE_ENV" not in names

        details = {f.name: f.detail for f in facts}
        assert details["NEXT_PUBLIC_API_URL"].startswith("client-exposed")
        assert details["VITE_API_URL"].startswith("client-exposed")
        assert details["API_URL"].startswith("server-side")

    def test_port_token_is_intentionally_ignored_in_env_facts(self, repo: Path) -> None:
        (repo / "src").mkdir()
        (repo / "src" / "app.js").write_text('const port = process.env["PORT"];')
        (repo / ".env.example").write_text("PORT=\n")

        facts = extract_env(repo)
        names = {f.name for f in facts}
        assert "PORT" not in names

    def test_env_fact_has_file_and_line(self, repo: Path) -> None:
        (repo / "src").mkdir()
        (repo / "src" / "app.js").write_text("const x = process.env.HOST;\n")
        (repo / ".env.example").write_text("HOST=localhost\n")

        facts = extract_env(repo)
        host_facts = [f for f in facts if f.name == "HOST"]
        assert len(host_facts) >= 1
        for f in host_facts:
            assert f.file
            assert f.line >= 0


class TestStage2PortsAndRoutes:
    """Acceptance check for the Stage 2 port + route extractors.

    This is intentionally a small manual-acceptance style set here, because
    the router/port fixtures are also the Stage 2 end-to-end input.
    """

    def test_vite_server_port_config(self, repo: Path) -> None:
        (repo / "package.json").write_text(
            json.dumps({"dependencies": {"react": "^19"}, "devDependencies": {"vite": "^6"}})
        )
        (repo / "vite.config.js").write_text(
            "export default defineConfig({ server: { port: 3000 } });\n"
        )

        from drift.extract_ports import extract_ports

        ports = extract_ports(repo)
        vite_ports = [p for p in ports if p.kind == "port" and p.file == "vite.config.js"]
        assert vite_ports, "expected vite server.port fact"
        assert any("3000" in p.detail for p in vite_ports), "expected port 3000 in vite config fact"


if _pytest is None:
    from pathlib import Path as _Path

    def _mini_next_app(tmp_path: _Path) -> _Path:
        repo = tmp_path / "next_app"
        repo.mkdir()
        (repo / "package.json").write_text(
            json.dumps(
                {
                    "name": "next-app",
                    "scripts": {"dev": "next dev", "build": "next build"},
                    "dependencies": {"next": "^15", "react": "^19", "prisma": "^6"},
                    "engines": {"node": ">=20"},
                }
            )
        )
        (repo / ".env.example").write_text("DATABASE_URL=\nNEXT_PUBLIC_SITE_URL=\n")
        (repo / "app").mkdir()
        (repo / "app" / "page.tsx").write_text(
            "export default function Page() { return process.env.NEXT_PUBLIC_SITE_URL; }"
        )
        return repo

    with tempfile.TemporaryDirectory() as _td:
        _tmp = _Path(_td)
        _fix = _mini_next_app(_tmp)
        assert detect(_fix) == "next_app"
        _pkg = extract_pkg(_fix)
        _pkg_names = {f.name for f in _pkg}
        for _name in ["dev", "build", "next", "react", "prisma", "node"]:
            assert _name in _pkg_names, f"missing pkg fact from mini next_app fixture: {_name}"
        _env = extract_env(_fix)
        _env_names = {f.name for f in _env}
        for _name in ["DATABASE_URL", "NEXT_PUBLIC_SITE_URL"]:
            assert _name in _env_names, f"missing env fact from mini next_app fixture: {_name}"
    print("mini next_app fixture facts OK")


class TestMiniNextAppFixture:
    """Acceptance check using a minimal next_app fixture that feeds Stage 2.

    This lives here because the fixture doubles as the Stage 2 end-to-end
    input, but the "fact correctness" assertion is owned by Member A.
    """

    @_pytest.fixture
    def fixture_repo(self, tmp_path: Path) -> Path:
        repo = tmp_path / "next_app"
        repo.mkdir()
        (repo / "package.json").write_text(
            json.dumps(
                {
                    "name": "next-app",
                    "scripts": {"dev": "next dev", "build": "next build"},
                    "dependencies": {"next": "^15", "react": "^19", "prisma": "^6"},
                    "engines": {"node": ">=20"},
                }
            )
        )
        (repo / ".env.example").write_text("DATABASE_URL=\nNEXT_PUBLIC_SITE_URL=\n")
        (repo / "app").mkdir()
        (repo / "app" / "page.tsx").write_text(
            "export default function Page() { return process.env.NEXT_PUBLIC_SITE_URL; }"
        )
        return repo

    def test_fixture_produces_correct_pkg_and_env_facts(self, fixture_repo: Path) -> None:
        assert detect(fixture_repo) == "next_app"

        pkg_facts = extract_pkg(fixture_repo)
        pkg_names = {f.name for f in pkg_facts}
        for name in ["dev", "build", "next", "react", "prisma", "node"]:
            assert name in pkg_names, f"missing pkg fact: {name}"

        env_facts = extract_env(fixture_repo)
        env_names = {f.name for f in env_facts}
        for name in ["DATABASE_URL", "NEXT_PUBLIC_SITE_URL"]:
            assert name in env_names, f"missing env fact: {name}"


class TestStage2ManualFixturePrinter:
    """Manual-acceptance helper that builds the full stage2 fixture and
    prints every route/port fact so the team can eyeball correctness.
    """

    def test_manual_stage2_fixture_output(self, repo: Path) -> None:
        import json as _json

        (repo / "package.json").write_text(_json.dumps({
            "name": "stage2-next",
            "scripts": {"dev": "next dev -p 3000", "start": "next start", "custom": "node server.js --port 4000"},
            "dependencies": {"next": "^15", "react": "^19"},
            "devDependencies": {"typescript": "^5"},
            "engines": {"node": ">=20"},
            "packageManager": "pnpm@9.0.0",
        }))
        (repo / ".nvmrc").write_text("20.11.0\n")
        (repo / "pnpm-lock.yaml").write_text("lockfileVersion: 9.0.0\n")
        (repo / "next.config.js").write_text(
            "/** @type {import('next').NextConfig} */\n"
            "const nextConfig = {\n"
            "  server: { port: 5000 },\n"
            "};\n"
            "module.exports = nextConfig;\n"
        )

        (repo / "src").mkdir()
        (repo / "src" / "server.js").write_text("const app = require('express')();\napp.listen(8000);\n")
        (repo / "src" / "dynamic.js").write_text("const port = process.env.PORT || 3000;\n")
        (repo / "src" / "server2.ts").write_text("const server = http.createServer(...);\nserver.listen( 9000 );\n")

        (repo / "app").mkdir()
        (repo / "app" / "api").mkdir()
        (repo / "app" / "api" / "users").mkdir()
        (repo / "app" / "api" / "users" / "route.ts").write_text(
            "import { NextResponse } from 'next/server';\n"
            "export async function GET() { return NextResponse.json({ ok: true }); }\n"
            "export async function POST() { return NextResponse.json({ ok: true }); }\n"
        )
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
        (repo / "app" / "(marketing)").mkdir()
        (repo / "app" / "(marketing)" / "page.tsx").write_text("export default function Page() { return null; }")
        (repo / "app" / "layout.tsx").write_text("export default function Layout() { return null; }")

        (repo / "pages").mkdir()
        (repo / "pages" / "api").mkdir()        (repo / "pages" / "api" / "legacy.js").write_text(
            "export default function handler(req, res) {\n"
            "  res.status(200).json({ ok: true });\n"
            "}\n"
        )
        (repo / "pages" / "api" / "items").mkdir()
        (repo / "pages" / "api" / "items" / "[slug].js").write_text(
            "export default function handler(req, res) {\n"
            "  res.status(200).json({ ok: true });\n"
            "}\n"
        )
        (repo / "pages" / "index.js").write_text("export default function Page() { return null; }")

        (repo / "src" / "express").mkdir()
        (repo / "src" / "express" / "app.js").write_text(
            "const express = require('express');\n"
            "const router = express.Router();\n"
            "app.get('/api/health', (req, res) => res.json({ ok: true }));\n"
            "router.post('/api/items', (req, res) => res.json({ ok: true }));\n"
            "app.use('/admin', router);\n"
        )

        from drift.extract_ports import extract_ports
        from drift.extract_routes import extract_routes

        routes = extract_routes(repo)
        ports = extract_ports(repo)

        routes_by_file = {r.file: [x for x in routes if x.file == r.file] for r in routes}
        ports_by_file = {p.file: [x for x in ports if x.file == p.file] for p in ports}

        assert any(r.kind == "route" for r in routes), "expected at least one route"
        assert any(p.kind == "port" for p in ports), "expected at least one port"
        assert "app\\api\\users\\route.ts" in routes_by_file, f"expected app/api/users route, got {list(routes_by_file)}"
        assert "app\\api\\users\\[id]\\route.ts" in routes_by_file, f"expected app/api/users/[id] route, got {list(routes_by_file)}"
        assert "app\\api\\posts\\(draft)\\route.ts" in routes_by_file, f"expected app/api/posts route, got {list(routes_by_file)}"
        assert "pages\\api\\legacy.js" in routes_by_file, f"expected pages/api/legacy.js route, got {list(routes_by_file)}"
        assert "pages\\api\\items\\[slug].js" in routes_by_file, f"expected pages/api/items/[slug].js route, got {list(routes_by_file)}"
        assert "src\\express\\app.js" in routes_by_file, f"expected express app.js routes, got {list(routes_by_file)}"
        assert "src\\server.js" in ports_by_file, f"expected src/server.js port, got {list(ports_by_file)}"
        assert "src\\dynamic.js" in ports_by_file, f"expected src/dynamic.js port, got {list(ports_by_file)}"
        assert "src\\server2.ts" in ports_by_file, f"expected src/server2.ts port, got {list(ports_by_file)}"
        assert "next.config.js" in ports_by_file, f"expected next.config.js port, got {list(ports_by_file)}"
        assert any(r.detail == "GET,POST" for r in routes), "expected GET,POST on users route"
        assert any(p.name == "dev" for p in ports), "expected dev script port"
        assert any(p.name == "custom" for p in ports), "expected custom script port"
        print("routes:")
        for r in routes:
            print(f"  - route {r.file:18} name={r.name!r:22} detail={r.detail!r:12}")
        print("ports:")
        for p in ports:
            print(f"  - port {p.file:14} name={p.name!r:14} detail={p.detail!r}")
