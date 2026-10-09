from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from .models import Fact

WebKind = Literal["next_app", "express_api", "vite_react", "other"]


def detect(repo: Path) -> WebKind:
    """Identify the web project type from package.json and common layout signals.

    Returns one of:
      - next_app
      - express_api
      - vite_react
      - other
    """
    pkg = _load_package_json(repo)
    if pkg is None:
        return "other"

    deps = {**(pkg.get("dependencies") or {}), **(pkg.get("devDependencies") or {})}

    if deps.get("next") is not None:
        return "next_app"

    if deps.get("express") is not None:
        return "express_api"

    if deps.get("vite") is not None or deps.get("react") is not None:
        # Prefer Vite signal when both are present.
        if deps.get("vite") is not None:
            return "vite_react"
        return "vite_react"

    return "other"


def is_web_project(repo: Path) -> bool:
    """True when the repo looks like a supported JS/TS web project."""
    pkg = _load_package_json(repo)
    if pkg is None:
        return False
    return detect(repo) != "other"


def _load_package_json(repo: Path) -> dict | None:
    pkg_path = repo / "package.json"
    if not pkg_path.is_file():
        return None
    try:
        return json.loads(pkg_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def not_web_error(repo: Path) -> str:
    """Exit message for repos without a usable package.json."""
    pkg = repo / "package.json"
    if not pkg.exists():
        return (
            f"No package.json found in {repo}.\n"
            "docs-drift-detector targets JS/TS web projects (Next.js, Express, Vite/React)."
        )
    return (
        f"package.json found in {repo}, but no supported web project detected.\n"
        "Supported stacks: Next.js, Express, Vite/React."
    )
