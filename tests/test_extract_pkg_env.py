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

        def test_port_token_is_intentionally_ignored(self, repo: Path) -> None:
            (repo / "src").mkdir()
            (repo / "src" / "app.js").write_text('const port = process.env["PORT"];')
            (repo / ".env.example").write_text("PORT=\n")

            facts = extract_env(repo)
            names = {f.name for f in facts}
            assert "PORT" not in names


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
