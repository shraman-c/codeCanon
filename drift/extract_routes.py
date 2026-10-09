from __future__ import annotations

import re
from pathlib import Path
from typing import Iterator

from .models import Fact

APP_ROUTER_METHOD = re.compile(r"(?i)export\s+(?:async\s+)?function\s+(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s*\(")
EXPRESS_ROUTE = re.compile(r"(?i)(?:app|router)\.(get|post|put|patch|delete)\s*\(\s*[\"'`]([/#~]?\s*[^\s,\)'\"]+)[\'\"]?\s*,")
EXPRESS_USE_PREFIX = re.compile(r"(?i)(?:app|router)\.use\s*\(\s*[\"'`]([/#~]?\s*[^\s,\)'\"]+)\s*,\s*(?:const|let|var)\s+(\w+)\s*=\s*express\.Router\(\)")


SKIP_DIRS = {"node_modules", ".next", "dist", "build", ".git", "coverage"}


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


def extract_routes(repo: Path) -> list[Fact]:
    """Extract route facts from Next App Router, Pages Router, and Express.

    - Next App Router: app/**/route.{ts,js}
    - Next Pages Router: pages/api/...
    - Express: (app|router).(get|post|put|patch|delete)('/...')
      plus same-file app.use('/prefix', router) when the router
      is created in the same file.
    """
    facts: list[Fact] = []

    facts.extend(_next_app_router(repo))
    facts.extend(_next_pages_router(repo))
    facts.extend(_express_routes(repo))

    return facts


def _next_app_router(repo: Path) -> list[Fact]:
    facts: list[Fact] = []
    app_dir = repo / "app"
    if not app_dir.is_dir():
        return facts

    for route_path in sorted(app_dir.rglob("route.*")):
        if route_path.suffix not in {".ts", ".js"}:
            continue
        rel = route_path.relative_to(repo)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue

        methods = _extract_app_router_methods(route_path)
        if not methods:
            continue

        url = _app_router_url(rel.parent)
        if not url:
            continue

        facts.append(
            Fact(
                kind="route",
                name=url,
                detail=",".join(methods),
                file=str(rel),
                line=0,
            )
        )

    return facts


def _next_pages_router(repo: Path) -> list[Fact]:
    facts: list[Fact] = []
    pages_api = repo / "pages" / "api"
    if not pages_api.is_dir():
        return facts

    for path in sorted(pages_api.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix not in {".ts", ".js"}:
            continue
        rel = path.relative_to(repo)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue

        methods_str = ','.join(methods) if methods else 'GET'
        facts.append(
            Fact(
                kind="route",
                name=_next_pages_router_url(path),
                detail=methods_str,
                file=str(rel),
                line=0,
            )
        )

    return facts


def _next_pages_router_url(path: Path) -> str:
    """Build a pages router URL from a path, always rooted under /api/..."""
    parts: list[str] = []
    current = path
    while current.name != "pages":
        if current.name in SKIP_DIRS:
            raise ValueError("unexpected SKIP_DIRS in pages router path")
        if current.name.startswith("[") and current.name.endswith("]") and current.name != "index":
            parts.append(":" + current.name[1:-1])
        else:
            parts.append(current.name)
        current = current.parent
    parts.reverse()
    return "/" + "/".join(parts)


def _express_routes(repo: Path) -> list[Fact]:
    facts: list[Fact] = []
    same_file_prefixes: dict[Path, list[str]] = {}

    for src in iter_source_files(repo):
        rel = src.relative_to(repo)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue

        text = src.read_text(encoding="utf-8", errors="replace")

        prefixes = _express_same_file_prefixes(src, text)
        if prefixes:
            same_file_prefixes[src] = prefixes

        for m in EXPRESS_ROUTE.finditer(text):
            raw = m.group(2).strip()
            detail = raw
            path = raw if raw.startswith("/") else "/" + raw

        method = m.group(1).upper()
        base_url = _prefix_for(src, same_file_prefixes.get(src, []))
        if base_url:
            url = base_url.rstrip("/") + path.lstrip("/")
        else:
            url = path
        if not url.startswith("http"):
            facts.append(
                Fact(
                    kind="route",
                    name=url,
                    detail=detail,
                    file=str(rel),
                    line=text[: m.start()].count("\n") + 1,
                )
            )

    for src, prefixes in same_file_prefixes.items():
        rel = src.relative_to(repo)
        for prefix in prefixes:
            facts.append(
                Fact(
                    kind="route",
                    name=prefix,
                    detail=f"prefix {prefix} (app.use same-file router)",
                    file=str(rel),
                    line=0,
                )
            )

    return facts


def _app_router_url(folder: Path) -> str | None:
    parts = []
    for p in folder.parts:
        if p == "app":
            continue
        if p.startswith("(") and p.endswith(")"):
            continue
        if p.startswith("[") and p.endswith("]"):
            parts.append(":" + p[1:-1])
        else:
            parts.append(p)

    if not parts:
        return None

    url = "/" + "/".join(parts)
    return url


def _extract_app_router_methods(path: Path) -> list[str]:
    methods: list[str] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return methods

    seen: set[str] = set()
    for m in APP_ROUTER_METHOD.finditer(text):
        name = m.group(1).upper()
        if name not in seen:
            seen.add(name)
            methods.append(name)

    return methods


def _guess_pages_router_methods(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ["GET"]

    if re.search(r"(?i)(?:app\.get|router\.get|req\.method|method ===)", text):
        return ["GET"]
    if re.search(r"(?i)(?:app\.post|router\.post|method === 'POST'|req\.method)", text):
        return ["GET", "POST"]
    return ["GET"]


def _express_same_file_prefixes(src: Path, text: str) -> list[str]:
    prefixes: list[str] = []
    router_names: set[str] = set()
    for m in re.finditer(r"(?i)(?:const|let|var)\s+(\w+)\s*=\s*express\.Router\(\);", text):
        router_names.add(m.group(1))

    for m in EXPRESS_USE_PREFIX.finditer(text):
        prefix = m.group(1).strip()
        router_var = m.group(2)
        if router_var in router_names:
            prefixes.append(prefix)

    return prefixes


def _prefix_for(src: Path, prefixes: list[str]) -> str:
    if not prefixes:
        return ""
    return prefixes[0] if len(prefixes) == 1 else ""
