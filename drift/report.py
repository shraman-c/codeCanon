from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import Claim, Fact, Finding


def write_report(
    repo_path: str,
    kind: str,
    mode: str,
    facts: list[Fact],
    claims: list[Claim],
    findings: list[Finding],
    model: dict[str, Any],
    output: Path,
    diff: str | None = None,
    ignored_paths: list[str] | None = None,
    files_read: int = 0,
    images_read: int = 0,
) -> None:
    """Write drift-report.json and drift-report.md per schema."""
    ignored_paths = ignored_paths or []

    stale_count = sum(1 for f in findings if f.status == "STALE")
    suspect_count = sum(1 for f in findings if f.status == "SUSPECT")
    ok_count = sum(1 for f in findings if f.status == "OK")

    payload = {
        "metadata": {
            "repo_path": repo_path,
            "kind": kind,
            "mode": mode,
            "diff": diff,
            "ignored_paths": sorted(ignored_paths),
            "stats": {
                "files_read": files_read,
                "images_read": images_read,
            },
        },
        "model": model,
        "facts": [f.__dict__ for f in facts],
        "claims": [c.to_dict() for c in claims],
        "findings": [
            {
                **f.to_dict(),
                "claim": f.claim.to_dict(),
            }
            for f in findings
        ],
    }

    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    md = _build_markdown(
        repo_name=Path(repo_path).name,
        kind=kind,
        findings=findings,
        model=model,
        stale_count=stale_count,
        suspect_count=suspect_count,
        ok_count=ok_count,
    )
    output.with_suffix(".md").write_text(md + "\n", encoding="utf-8")


def _build_markdown(
    repo_name: str,
    kind: str,
    findings: list[Finding],
    model: dict[str, Any],
    stale_count: int,
    suspect_count: int,
    ok_count: int,
) -> str:
    lines = [f"# drift-report — {repo_name}", ""]
    lines.append(f"Project type: `{kind}`  ")
    lines.append(f"Findings: **{len(findings)}** (STALE {stale_count}, SUSPECT {suspect_count}, OK {ok_count})")
    lines.append(f"Model: `{model.get('id', 'unknown')}` ({model.get('mode', 'unknown')})")
    lines.append("")
    lines.append("| Status | Doc | Line | Claim | Reason |")
    lines.append("|---|---|---|---|---|")

    for f in findings:
        claim_txt = f.claim.text.replace("|", "\\|")
        reason = f.reason.replace("|", "\\|")
        doc_name = Path(f.claim.doc_file).name
        lines.append(f"| {f.status} | {doc_name} | {f.claim.line} | {claim_txt} | {reason} |")

    lines.append("")
    lines.append("## Patches")
    any_patch = False
    for f in findings:
        if f.patch:
            any_patch = True
            lines.append(f"\n### {Path(f.claim.doc_file).name}:{f.claim.line} — {f.claim.text}\n")
            lines.append("```diff")
            lines.append(f.patch.rstrip())
            lines.append("```")
    if not any_patch:
        lines.append("\n_No patches generated._")

    return "\n".join(lines)