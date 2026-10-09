from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

from .models import Fact


SKIP_DIRS = {
    "node_modules",
    ".next",
    "dist",
    "build",
    ".git",
    "coverage",
}


def iter_source_files(repo: Path) -> Iterator[Path]:
    """Yield JS/TS source files, skipping generated/ignored dirs."""
    if not repo.is_dir():
        return
    for path in sorted(repo.rglob("*")):
        if not path.is_file():
            continue
        if path.name.startswith("."):
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}:
            yield path


def extract_pkg(repo: Path) -> list[Fact]:
    """Extract npm_script, dependency, and engine facts from package.json + .nvmrc."""
    facts: list[Fact] = []
    pkg_path = repo / "package.json"
    pkg = _load_json(pkg_path) if pkg_path.is_file() else {}

    scripts = pkg.get("scripts") or {}
    for name, command in scripts.items():
        facts.append(
            Fact(
                kind="npm_script",
                name=name,
                detail=command,
                file=str(pkg_path.relative_to(repo)),
                line=0,
            )
        )

    for dep_type in ("dependencies", "devDependencies"):
        deps = pkg.get(dep_type) or {}
        for name, spec in deps.items():
            detail = "" if spec is None else str(spec)
            facts.append(
                Fact(
                    kind="dependency",
                    name=name,
                    detail=detail,
                    file=str(pkg_path.relative_to(repo)),
                    line=0,
                )
            )

    engines = pkg.get("engines") or {}
    for key, spec in engines.items():
        facts.append(
            Fact(
                kind="engine",
                name=key,
                detail=str(spec),
                file=str(pkg_path.relative_to(repo)),
                line=0,
            )
        )

    facts.extend(_nvmrc_facts(repo))

    return facts


def _nvmrc_facts(repo: Path) -> list[Fact]:
    nvmrc = repo / ".nvmrc"
    if not nvmrc.is_file():
        return []
    text = nvmrc.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return []
    return [
        Fact(
            kind="engine",
            name="node",
            detail=text,
            file=".nvmrc",
            line=0,
        )
    ]


def package_manager(repo: Path) -> str | None:
    """Infer the package manager from lockfile presence.

    Returns one of: npm, pnpm, yarn, bun, or None.
    """
    lockfiles = {
        "npm": {"package-lock.json"},
        "pnpm": {"pnpm-lock.yaml"},
        "yarn": {"yarn.lock"},
        "bun": {"bun.lockb"},
    }

    found: set[str] = set()
    root = repo if repo.is_dir() else repo.parent
    for name in root.iterdir():
        if name.is_file() and name.name in {k for group in lockfiles.values() for k in group}:
            found.add(name.name)

    for pm, names in lockfiles.items():
        if names & found:
            return pm
    return None


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
