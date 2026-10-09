from __future__ import annotations

import re
from pathlib import Path
from typing import Iterator

from .models import Fact

SourceFileSuffixes = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}


def extract_env(repo: Path) -> list[Fact]:
    """Extract env_var facts from source files and .env.example."""
    facts: dict[str, Fact] = {}

    # Code references first.
    for path in _code_paths(repo):
        for env_name in _env_names_in_file(path):
            if env_name in _FACT_IGNORE or env_name in _FACT_IGNORE_PORT_TOKENS:
                continue
            detail = _exposure_detail(env_name, path)
            existing = facts.get(env_name)
            if existing is None:
                facts[env_name] = Fact(
                    kind="env_var",
                    name=env_name,
                    detail=detail,
                    file=str(path.relative_to(repo)),
                    line=_source_line(path, env_name),
                )
            else:
                merged = _exposure_detail(env_name, path)
                if merged.startswith("client-exposed"):
                    facts[env_name] = Fact(
                        kind=existing.kind,
                        name=existing.name,
                        detail=merged,
                        file=str(path.relative_to(repo)),
                        line=_source_line(path, env_name),
                    )

    # .env.example keys supplement code facts.
    for env_name, detail in _env_example_keys(repo):
        if env_name in _FACT_IGNORE or env_name in _FACT_IGNORE_PORT_TOKENS:
            continue
        existing = facts.get(env_name)
        if existing is None:
            facts[env_name] = Fact(
                kind="env_var",
                name=env_name,
                detail=detail,
                file=".env.example",
                line=0,
            )
        elif existing.detail.startswith("server-side"):
            facts[env_name] = Fact(
                kind=existing.kind,
                name=existing.name,
                detail=detail,
                file=str((repo / ".env.example").relative_to(repo)),
                line=0,
            )

    return list(facts.values())


def _code_paths(repo: Path) -> Iterator[Path]:
    for path in sorted(repo.rglob("*")):
        if not path.is_file():
            continue
        if path.name.startswith("."):
            continue
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        if path.suffix in SourceFileSuffixes:
            yield path


def _env_names_in_file(path: Path) -> Iterator[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    seen: set[str] = set()
    for m in _ENV_PATTERN.finditer(text):
        name = m.group(1) or m.group(2) or m.group(3)
        if name is None:
            continue
        if not name or name in seen:
            continue
        seen.add(name)
        if _is_placeholder_token(name):
            continue
        yield name


_ENV_PATTERN = re.compile(
    r"""
    (?:
        process\.env\.([A-Za-z_][A-Za-z0-9_]*)
        |
        process\.env\s*\[\s*['"]([A-Za-z_][A-Za-z0-9_]*)['"]\s*\]
        |
        import\.meta\.env\.([A-Za-z_][A-Za-z0-9_]*)
    )
    """,
    re.VERBOSE,
)


def _is_placeholder_token(name: str) -> bool:
    lowered = name.lower()
    if lowered.startswith("your_") or lowered.startswith("your-"):
        return True
    if name.startswith("<") and name.endswith(">"):
        return True
    if re.fullmatch(r"[xX*-]+", name):
        return True
    return False


def _exposure_detail(name: str, path: Path) -> str:
    if name.startswith("NEXT_PUBLIC_"):
        return "client-exposed (Next.js)"
    if name.startswith("VITE_"):
        return "client-exposed (Vite)"
    return "server-side"


def _source_line(path: Path, name: str) -> int:
    normalized = re.sub(r"\s+", " ", path.read_text(encoding="utf-8", errors="replace"))
    for lineno, line in enumerate(normalized.splitlines(), start=1):
        if re.search(rf"\b{re.escape(name)}\b", line):
            return lineno
    return 1


def _env_example_keys(repo: Path) -> Iterator[tuple[str, str]]:
    example = repo / ".env.example"
    if not example.is_file():
        return
    for lineno, line in enumerate(example.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        cleaned = line.split("#", 1)[0].strip()
        if "=" not in cleaned:
            continue
        name, _, value = cleaned.partition("=")
        name = name.strip()
        value = value.strip()
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
            continue
        if _is_placeholder_token(name):
            continue
        detail = _env_example_detail(name, value)
        yield name, detail


def _env_example_detail(name: str, value: str) -> str:
    if value:
        return f"example value in .env.example: {value}"
    return "key declared in .env.example, no example value"


def is_client_exposed(fact: Fact) -> bool:
    return fact.name.startswith("NEXT_PUBLIC_") or fact.name.startswith("VITE_")


# Explicitly ignored env names for fact extraction.
# Keep general-purpose OS/runtime tokens out of drift findings.
_FACT_IGNORE = {
    "NODE_ENV",
    "HOME",
    "PATH",
    "CI",
}

# Common deployment port tokens that are intentionally excluded from
# env-var drift findings because they are not meaningful doc claims.
# Common deployment port tokens that are intentionally excluded from
# env-var drift findings because they are not meaningful doc claims.
_FACT_IGNORE_PORT_TOKENS = {
    "PORT",
}



_SKIP_DIRS = {
    "node_modules",
    ".next",
    "dist",
    "build",
    ".git",
    "coverage",
}
