from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from .models import Claim


@dataclass
class ExtractContext:
    in_fenced_block: bool = False
    fence_char: str = ""
    fence_len: int = 0
    paragraph_lines: list[str] = None

    def __post_init__(self):
        if self.paragraph_lines is None:
            self.paragraph_lines = []

    def add_line(self, line: str) -> None:
        self.paragraph_lines.append(line)
        if len(self.paragraph_lines) > 10:
            self.paragraph_lines.pop(0)

    def get_context(self, max_chars: int = 400) -> str:
        text = " ".join(self.paragraph_lines).strip()
        if len(text) > max_chars:
            text = text[:max_chars].rsplit(" ", 1)[0] + "..."
        return text


def scan_file(filepath: Path) -> Iterator[Claim]:
    ctx = ExtractContext()
    line_num = 0

    with filepath.open("r", encoding="utf-8", errors="ignore") as f:
        for raw_line in f:
            line_num += 1
            line = raw_line.rstrip("\n")

            if not ctx.in_fenced_block:
                fence_match = re.match(r"^(\s*)([`~]{3,})(\w*)", line)
                if fence_match:
                    ctx.in_fenced_block = True
                    ctx.fence_char = fence_match.group(2)[0]
                    ctx.fence_len = len(fence_match.group(2))
                    continue
            else:
                fence_match = re.match(rf"^(\s*)({re.escape(ctx.fence_char)}){{{ctx.fence_len},}}", line)
                if fence_match:
                    ctx.in_fenced_block = False
                    continue

            ctx.add_line(line)

            source = "text"

            for claim in extract_claims_from_line(line, line_num, filepath, source, ctx.get_context()):
                yield claim

            for claim in extract_route_claims_from_line(line, line_num, filepath, source, ctx.get_context()):
                yield claim


def extract_claims_from_line(
    line: str,
    line_num: int,
    filepath: Path,
    source: str,
    context: str,
) -> Iterator[Claim]:
    pkg_managers = r"(?:npm|pnpm|yarn|bun)\s+(?:run\s+)?(\w+)"
    for m in re.finditer(pkg_managers, line):
        cmd = m.group(1)
        yield Claim(
            kind="npm_script",
            text=f"{m.group(0)}",
            doc_file=str(filepath),
            line=line_num,
            context=context,
            source=source,
        )

    env_pattern = r"(?:^|\s)([A-Z_][A-Z0-9_]*)\s*=\s*([^\s#]+)"
    for m in re.finditer(env_pattern, line):
        if not m.group(1).startswith("_"):
            yield Claim(
                kind="env_var",
                text=f"{m.group(1)}={m.group(2)}",
                doc_file=str(filepath),
                line=line_num,
                context=context,
                source=source,
            )

    env_placeholder = r"(?:^|\s)(YOUR_[A-Z_]+|<your-[^>]+>)\b"
    for m in re.finditer(env_placeholder, line):
        yield Claim(
            kind="env_var",
            text=m.group(1),
            doc_file=str(filepath),
            line=line_num,
            context=context,
            source=source,
        )

    port_patterns = [
        r"localhost:(\d{2,5})",
        r"port\s+(\d{2,5})",
        r"(?:^|\s)PORT\s*=\s*(\d{2,5})",
        r":(\d{2,5})(?=\s|$|/)",
    ]
    for pattern in port_patterns:
        for m in re.finditer(pattern, line, re.IGNORECASE):
            port = m.group(1)
            if 10 <= int(port) <= 65535:
                text = m.group(0)
                if pattern == port_patterns[2]:
                    text = f"PORT={port}"
                yield Claim(
                    kind="port",
                    text=text,
                    doc_file=str(filepath),
                    line=line_num,
                    context=context,
                    source=source,
                )

    node_pattern = r"node\s+(?:version\s+)?(?:>=?\s*)?(\d{1,2}(?:\.\d+){1,2})"
    for m in re.finditer(node_pattern, line, re.IGNORECASE):
        version = m.group(1)
        major = int(version.split(".")[0])
        if major >= 16:
            yield Claim(
                kind="engine",
                text=f"node {version}",
                doc_file=str(filepath),
                line=line_num,
                context=context,
                source=source,
            )


def extract_route_claims_from_line(
    line: str,
    line_num: int,
    filepath: Path,
    source: str,
    context: str,
) -> Iterator[Claim]:
    route_patterns = [
        (r"\b(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+(/[^\s\"'>`)]+)", "method_path"),
        (r"curl\s+(?:-[XLM]\s+)?['\"]?(?:([A-Z]+)\s+)?([^\s\"'>`)]+)", "curl"),
        (r"fetch\(['\"]([^'\"]+)['\"]", "fetch"),
        (r"[`'\"]?(/api/[^`'\"]+)[`'\"]?", "api_path"),
    ]

    for pattern, claim_type in route_patterns:
        for m in re.finditer(pattern, line):
            if claim_type == "method_path":
                method, path = m.groups()
                text = f"{method} {path}"
            elif claim_type == "curl":
                method = m.group(1) or "GET"
                path = m.group(2)
                text = f"curl {method} {path}"
            elif claim_type == "fetch":
                path = m.group(1)
                text = f"fetch('{path}')"
            else:
                path = m.group(1)
                text = path

            yield Claim(
                kind="route",
                text=text,
                doc_file=str(filepath),
                line=line_num,
                context=context,
                source=source,
            )


def extract_claims_from_files(paths: list[Path]) -> list[Claim]:
    claims = []
    for path in paths:
        if path.is_file() and path.suffix in {".md", ".mdx", ".txt", ".rst"}:
            claims.extend(scan_file(path))
        elif path.is_dir():
            for ext in ("*.md", "*.mdx", "*.txt", "*.rst"):
                claims.extend(scan_file(p) for p in path.rglob(ext))
    return claims