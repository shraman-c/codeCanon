from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterator

from .models import Fact

SKIP_DIRS = {"node_modules", ".next", "dist", "build", ".git", "coverage"}

SCRIPT_PORTFILE = re.compile(r"""
(?i)
(?:-p\s+([\d]+)               #   -p <port>
|  --port\s+([\d]+))          #   --port <port>
""", re.VERBOSE)
LISTEN = re.compile(r"""(?i)\.listen\(((?:\s*)?(?:\d+)\s*)\)""")
ENV_PORT_EXPR = re.compile(r"""(?i)process\.env\.PORT\s*\|\|\s*(\d+)""")
VITE_SERVER_PORT = re.compile(r"""(?is)server\s*:\s*\{[^}]*port\s*:\s*([\d]+)""")


def iter_source_files(repo: Path) -> Iterator[Path]:
    """Yield JS/TS source files, skipping generated/ignored dirs.

    Extractors should share this list so skip rules stay consistent.
    """
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


def extract_ports(repo: Path) -> list[Fact]:
    """Extract port facts from:

    - source files using .listen(<N>), process.env.PORT || <N>
    - npm scripts with -p <N> or --port <N>
    - next.config.js/next.config.mjs `server.port`
    - vite.config.js/vite.config.ts `server.port`
    """
    facts: list[Fact] = []
    seen: set[tuple[str, str]] = set()

    for src in iter_source_files(repo):
        facts.extend(_ports_from_file(src, repo))

    for script, command in _npm_scripts(repo).items():
        m = SCRIPT_PORTFILE.search(command)
        if m:
            port = m.group(1) or m.group(2)
            if port and (script, port) not in seen:
                facts.append(
                    Fact(
                        kind="port",
                        name=script,
                        detail=f"script {script} listens on :{port}",
                        file="package.json",
                        line=0,
                    )
                )
                seen.add((script, port))

    facts.extend(_config_port_facts(repo))
    return facts


def _ports_from_file(path: Path, repo: Path) -> list[Fact]:
    facts: list[Fact] = []
    relative = str(path.relative_to(repo))
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return facts

    for lineno, line in enumerate(text.splitlines(), start=1):
        m = LISTEN.search(line)
        if m and (match := re.search(r"\d+", m.group(1) or m.group(2) or "")):
            port = match.group(0)
            facts.append(
                Fact(
                    kind="port",
                    name=relative,
                    detail=f"{relative}:{lineno} .listen():{port}",
                    file=relative,
                    line=lineno,
                )
            )
            continue

        m = ENV_PORT_EXPR.search(line)
        if m:
            port = m.group(1)
            facts.append(
                Fact(
                    kind="port",
                    name=relative,
                    detail=f"{relative}:{lineno} PORT fallback :{port}",
                    file=relative,
                    line=lineno,
                )
            )

    return facts


def _npm_scripts(repo: Path) -> dict[str, str]:
    pkg = _load_json(repo / "package.json")
    return dict(pkg.get("scripts") or {})


def _config_port_facts(repo: Path) -> list[Fact]:
    facts: list[Fact] = []

    for cfg in (
        repo / "next.config.js",
        repo / "next.config.mjs",
        repo / "vite.config.js",
        repo / "vite.config.ts",
    ):
        if not cfg.is_file():
            continue
        try:
            text = cfg.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        for m in VITE_SERVER_PORT.finditer(text):
            port = m.group(1)
            facts.append(
                Fact(
                    kind="port",
                    name=cfg.name,
                    detail=f"{cfg.name} server.port = {port}",
                    file=str(cfg.relative_to(repo)),
                    line=text[: m.start()].count("\n") + 1,
                )
            )

    return facts


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return {}
