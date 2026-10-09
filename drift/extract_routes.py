from __future__ import annotations

import re
from pathlib import Path
from typing import Iterator

from .models import Fact

APP_ROUTER_METHOD = re.compile(
    r"(?i)export\s+(?:async\s+)?function\s+(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s*\("
)
# app.get('/path', handler) | router.post("/path", handler) — group 1 receiver, 2 method, 3 path
EXPRESS_ROUTE = re.compile(
    r"(?i)\b(app|router)\s*\.\s*(get|post|put|patch|delete)\s*\(\s*[\"'`]([^\"'`]+?)[\"'`]"
)
# app.use('/prefix', router) — group 1 receiver, 2 prefix, 3 mounted var
EXPRESS_USE_PREFIX = re.compile(
    r"(?i)\b(app|router)\s*\.\s*use\s*\(\s*[\"'`]([^\"'`]+?)[\"'`]\s*,\s*([A-Za-z_$][\w$]*)"
)
# const router = express.Router() — declares a router variable in this file
EXPRESS_ROUTER_DECL = re.compile(
    r"(?i)(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*express\s*\.\s*Router\s*\("
)

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

    - Next App Router: app/**/route.{ts,js} → URL from the folder path
      ([id] → :id, "(group)" folders ignored), methods from
      ``export async function GET/POST/...``.
    - Next Pages Router: pages/api/** → /api/....
    - Express: (app|router).(get|post|put|patch|delete)('/...') plus a
      same-file ``app.use('/prefix', router)`` mount. Cross-file prefixes
      are left unresolved so the matcher marks them SUSPECT.
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
                file=rel.as_posix(),
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

        methods = _guess_pages_router_methods(path)
        facts.append(
            Fact(
                kind="route",
                name=_next_pages_router_url(rel),
                detail=",".join(methods) if methods else "GET",
                file=rel.as_posix(),
                line=0,
            )
        )

    return facts


def _next_pages_router_url(rel: Path) -> str:
    """Build a Pages Router URL from a repo-relative path.

    ``pages/api/items/[slug].js`` → ``/api/items/[slug].js``
    Directory segments wrapped in brackets become ``:seg``; file names are
    kept verbatim so the matcher can normalise them.
    """
    parts = list(rel.parts)
    if "pages" in parts:
        parts = parts[parts.index("pages") + 1:]

    segments: list[str] = []
    for part in parts[:-1]:  # directories
        if part.startswith("[") and part.endswith("]"):
            segments.append(":" + part[1:-1])
        else:
            segments.append(part)
    if parts:
        segments.append(parts[-1])  # file name verbatim

    return "/" + "/".join(segments)


def _express_routes(repo: Path) -> list[Fact]:
    facts: list[Fact] = []

    for src in iter_source_files(repo):
        rel = src.relative_to(repo)
        try:
            text = src.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        prefixes = _express_same_file_prefixes(text)

        for m in EXPRESS_ROUTE.finditer(text):
            receiver = m.group(1).lower()
            method = m.group(2).upper()
            raw = m.group(3).strip()
            path = raw if raw.startswith("/") else "/" + raw

            # Same-file mount only; imported routers keep their raw path so
            # the matcher can flag them as SUSPECT.
            prefix = prefixes.get(receiver, "")
            url = prefix.rstrip("/") + path if prefix else path

            facts.append(
                Fact(
                    kind="route",
                    name=url,
                    detail=method,
                    file=rel.as_posix(),
                    line=text[: m.start()].count("\n") + 1,
                )
            )

    return facts


def _express_same_file_prefixes(text: str) -> dict[str, str]:
    """Map receiver var → mount prefix for routers declared in this file.

    ``const router = express.Router(); ... app.use('/admin', router)``
    yields ``{"router": "/admin"}``. Vars that are imported from another
    file are deliberately excluded (cross-file prefixes stay unresolved).
    """
    declared = set(EXPRESS_ROUTER_DECL.findall(text))

    prefixes: dict[str, str] = {}
    for m in EXPRESS_USE_PREFIX.finditer(text):
        prefix, var = m.group(2).strip(), m.group(3)
        if var in declared and var not in prefixes:
            prefixes[var] = prefix.rstrip("/")

    # ``app.use('/admin', router)`` also mounts plain ``app`` routes? No —
    # only the mounted var receives the prefix.
    return prefixes


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

    return "/" + "/".join(parts)


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

    has_post = re.search(r"(?i)method\s*===\s*[\"']POST[\"']|req\.method", text) and re.search(
        r"(?i)[\"']POST[\"']", text
    )
    if has_post:
        return ["GET", "POST"]
    return ["GET"]
