from __future__ import annotations

import datetime
import json
import re
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
    """Write drift-report.json and drift-report.md per schema and rich styling."""
    ignored_paths = ignored_paths or []

    # 1. Filter / separate noise fragments from real findings
    real_findings: list[Finding] = []
    skipped_noise: list[tuple[Finding, str]] = []

    for f in findings:
        noise_reason = _check_noise_fragment(f)
        if noise_reason:
            skipped_noise.append((f, noise_reason))
        else:
            real_findings.append(f)

    broken = [f for f in real_findings if f.status == "STALE"]
    check = [f for f in real_findings if f.status == "SUSPECT"]
    verified = [f for f in real_findings if f.status == "OK"]

    broken_count = len(broken)
    check_count = len(check)
    verified_count = len(verified)
    skipped_count = len(skipped_noise)
    total_evaluated = broken_count + check_count + verified_count

    accuracy_pct = (
        round((verified_count / max(1, total_evaluated)) * 100)
        if total_evaluated > 0
        else 100
    )

    if broken_count > 0:
        verdict_status = f"{broken_count} high-priority problems in your docs"
        verdict_summary = "Needs attention"
    elif check_count > 0:
        verdict_status = f"{check_count} potential renames to verify"
        verdict_summary = "Check recommended"
    else:
        verdict_status = "docs match codebase facts!"
        verdict_summary = "All clear"

    # Count distinct docs checked
    doc_paths = {f.claim.doc_file for f in findings}
    if not doc_paths:
        doc_paths = {c.doc_file for c in claims}
    docs_checked_count = max(len(doc_paths), files_read, 1 if findings else 0)

    # 2. Build JSON payload
    payload = {
      "metadata": {
        "repo_path": repo_path,
        "kind": kind,
        "mode": mode,
        "diff": diff,
        "ignored_paths": sorted(ignored_paths),
        "stats": {
          "files_read": docs_checked_count,
          "images_read": images_read,
          "total_claims": len(claims),
          "broken": broken_count,
          "check": check_count,
          "verified": verified_count,
          "skipped": skipped_count,
          "accuracy_pct": accuracy_pct,
        },
      },
      "summary": {
        "verdict": verdict_summary,
        "accuracy_pct": accuracy_pct,
        "broken_count": broken_count,
        "check_count": check_count,
        "verified_count": verified_count,
        "skipped_count": skipped_count,
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
      "skipped_fragments": [
        {
          "where": f"{Path(f.claim.doc_file).name} L{f.claim.line}",
          "text": f.claim.text,
          "why_skipped": reason,
        }
        for f, reason in skipped_noise
      ],
    }

    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # 3. Build rich Markdown
    md = _build_markdown(
        repo_name=Path(repo_path).name,
        kind=kind,
        docs_count=docs_checked_count,
        broken=broken,
        check=check,
        verified=verified,
        skipped_noise=skipped_noise,
        accuracy_pct=accuracy_pct,
        model=model,
    )
    output.with_suffix(".md").write_text(md + "\n", encoding="utf-8")


def _check_noise_fragment(f: Finding) -> str | None:
    """Identify false-positive noise fragments to transparently categorize as skipped."""
    txt = f.claim.text.strip()
    kind = f.claim.kind

    # Port noise: numbers <= 100 not matching standard ports, or :30 from timestamps
    if kind == "port":
        m = re.search(r"(\d+)", txt)
        if m:
            val = int(m.group(1))
            if val < 80 and val not in (21, 22, 25, 53):
                return "number too small to be a port (likely a line number or timestamp fragment)"
        if txt.startswith(":") and len(txt) <= 4:
            return "number too small to be a port (likely a line number or timestamp fragment)"

    # Route noise: source code files (.ts/.js/.tsx), wildcards, or curl flags without paths
    if kind == "route":
        if re.search(r"\.(?:ts|tsx|js|jsx|json|py|md|css|html)\b", txt, re.IGNORECASE):
            return "source file path, not a URL route"
        if "*" in txt:
            return "wildcard pattern, not a concrete endpoint"
        if txt.lower().startswith("curl ") and not re.search(r"/(?:api|v\d+)/", txt):
            return "curl/shell fragment, no URL path"
        if re.search(r"curl\s+[A-Z]+\s+against\b", txt, re.IGNORECASE):
            return "curl/shell fragment, no URL path"

    # Env var noise: prose or placeholders
    if kind == "env_var":
        if txt in ("URL=the", "PORT=the") or txt.endswith("=the"):
            return "name too generic to judge (likely prose)"

    return None


def _build_markdown(
    repo_name: str,
    kind: str,
    docs_count: int,
    broken: list[Finding],
    check: list[Finding],
    verified: list[Finding],
    skipped_noise: list[tuple[Finding, str]],
    accuracy_pct: int,
    model: dict[str, Any],
) -> str:
    lines: list[str] = []

    # Date
    today = datetime.date.today().isoformat()
    real_findings = broken + check + verified
    total_claims = len(real_findings)

    # Model line
    model_id = model.get("id", "none")
    mode_str = model.get("mode", "api")
    if "disabled" in model_id:
        model_display = "none (deterministic only)"
    else:
        model_display = f"{model_id} ({mode_str})"

    lines.append(f"# 📄 Docs Drift Report: {repo_name}")
    lines.append("")
    lines.append(
        f"> **{docs_count} docs** checked · **{total_claims} claims** verified · stack `{kind}` · model {model_display} · {today}"
    )
    lines.append("")

    # Verdict
    lines.append("## Verdict")
    lines.append("")
    broken_count = len(broken)
    check_count = len(check)
    verified_count = len(verified)
    skipped_count = len(skipped_noise)

    if broken_count > 0:
        lines.append(f"🔴 **Needs attention**: {broken_count} high-priority problems in your docs")
    elif check_count > 0:
        lines.append(f"🟡 **Check recommended**: {check_count} potential renames to verify")
    else:
        lines.append("🟢 **All clear**: docs match codebase facts!")
    lines.append("")

    # Progress bar
    blocks = round(accuracy_pct / 10)
    bar = "█" * blocks + "░" * (10 - blocks)
    lines.append(f"**Docs accuracy: {accuracy_pct}%** `{bar}`")
    lines.append("")

    lines.append("| 🔴 Broken | 🟡 Check | 🟢 Verified | ⚪ Skipped as noise |")
    lines.append("|:-:|:-:|:-:|:-:|")
    lines.append(
        f"| **{broken_count}** problems | **{check_count}** to check | **{verified_count}** claims | **{skipped_count}** fragments |"
    )
    lines.append("")

    # Heads-up note if needed
    broken_routes = [f for f in broken if f.claim.kind == "route"]
    verified_routes = [f for f in verified if f.claim.kind == "route"]
    if broken_routes:
        lines.append(
            f"> ⚠️ **Heads-up:** {len(broken_routes)} documented endpoints were not found, while {len(verified_routes)} others matched. If you know some of these exist, the route detector may be missing a handler style (for example wrapped or re-exported handlers). Run the quick check under *Endpoints* before editing docs."
        )
        lines.append("")

    # Fix these first (top 5 broken)
    if broken:
        lines.append("## 🎯 Fix these first")
        lines.append("")
        for idx, f in enumerate(broken[:5], 1):
            category = _category_name(f.claim.kind)
            doc_name = Path(f.claim.doc_file).name
            lines.append(
                f"{idx}. 🔴 **{category} `{f.claim.text}`**: {f.reason}. (`{doc_name}` L{f.claim.line})"
            )
        lines.append("")

    # Broken section
    lines.append("## 🔴 Broken: docs describe things that aren't in the code")
    lines.append("")

    if not broken:
        lines.append("_No broken documentation claims detected._")
        lines.append("")
    else:
        # Group by category
        categories = [
            ("Endpoints", "route"),
            ("Ports", "port"),
            ("Environment variables", "env_var"),
            ("Scripts", "npm_script"),
            ("Dependencies", "dependency"),
            ("Runtime engines", "engine"),
        ]

        for cat_title, cat_kind in categories:
            items = [f for f in broken if f.claim.kind == cat_kind]
            if not items:
                continue

            lines.append(f"### {cat_title} ({len(items)})")
            lines.append("")
            lines.append("| Priority | Docs say | Where | What's wrong |")
            lines.append("|:-:|---|---|---|")

            for f in items:
                priority = "High" if cat_kind in ("route", "npm_script") else "Medium"
                doc_name = Path(f.claim.doc_file).name
                claim_txt = f.claim.text.replace("|", "\\|")
                reason = f.reason.replace("|", "\\|")
                lines.append(f"| {priority} | `{claim_txt}` | `{doc_name}` L{f.claim.line} | {reason} |")

            lines.append("")
            lines.append(
                f"**What to do:** Update or remove the {cat_title.lower()} in the docs. If it should exist, check whether it was deleted by mistake."
            )
            lines.append("")
            # Sample quick check
            sample_term = re.sub(r"^[A-Z]+\s+", "", items[0].claim.text).strip("`'\"/:")
            if sample_term:
                lines.append(f"> 🔎 Quick check: `git grep -n \"{sample_term}\"`.")
                lines.append("")

    # Check: close, but not quite right
    lines.append("## 🟡 Check: close, but not quite right")
    lines.append("")
    if not check:
        lines.append("_No near-match discrepancies found._")
        lines.append("")
    else:
        lines.append("These look like a rename or typo. The docs say one thing, the code has something very similar.")
        lines.append("")
        lines.append("| Docs say | Code has | Match | Suggested fix | Where |")
        lines.append("|---|---|:-:|---|---|")

        for f in check:
            doc_name = Path(f.claim.doc_file).name
            evidence_name = f.evidence[0].name if f.evidence else "similar item"
            # Extract similarity % if in reason
            sim_match = re.search(r"similarity=([0-9.]+)", f.reason)
            pct_str = f"{int(float(sim_match.group(1)) * 100)}%" if sim_match else "85%"
            suggested = f"Update to `{evidence_name}`"
            lines.append(
                f"| `{f.claim.text}` | `{evidence_name}` | {pct_str} | {suggested} | `{doc_name}` L{f.claim.line} |"
            )
        lines.append("")

    # Screenshots
    lines.append("## 🖼️ Screenshots")
    lines.append("")
    image_findings = [f for f in real_findings if f.claim.source == "image"]
    if not image_findings:
        lines.append("_Skipped: screenshot reading needs Gemma 4. Run without `--no-llm` / `--no-images` to enable it._")
    else:
        lines.append("| Status | Image Path | Quote | Reason |")
        lines.append("|---|---|---|---|")
        for f in image_findings:
            lines.append(
                f"| {f.status} | `{f.claim.image_path}` | `{f.claim.text}` | {f.reason} |"
            )
    lines.append("")

    # Patches
    lines.append("## 🩹 Patches")
    lines.append("")
    patched_findings = [f for f in real_findings if f.patch]
    if patched_findings:
        for f in patched_findings:
            doc_name = Path(f.claim.doc_file).name
            lines.append(f"### `{doc_name}:{f.claim.line}` — `{f.claim.text}`")
            lines.append("```diff")
            lines.append(f.patch.rstrip())
            lines.append("```")
            lines.append("")
    else:
        lines.append("No patch file was generated. Suggested one-line edits:")
        lines.append("")
        if check:
            for f in check:
                doc_name = Path(f.claim.doc_file).name
                evidence_name = f.evidence[0].name if f.evidence else "code name"
                lines.append(f"- `{doc_name}` L{f.claim.line}: replace `{f.claim.text}` with `{evidence_name}`")
            lines.append("")
        else:
            lines.append("_No patches generated._")
            lines.append("")
        lines.append("> 💡 Gemma 4 is switched off for this run. Re-run without `--no-llm` to get ready-to-apply `git apply` patches.")
        lines.append("")

    # Health by document
    lines.append("## 📊 Health by document")
    lines.append("")
    lines.append("| Document | Accuracy | 🔴 | 🟡 | 🟢 |")
    lines.append("|---|---|:-:|:-:|:-:|")

    # Group by doc_name
    by_doc: dict[str, list[Finding]] = {}
    for f in real_findings:
        doc_name = Path(f.claim.doc_file).name
        by_doc.setdefault(doc_name, []).append(f)

    if not by_doc and docs_count > 0:
        # If no real findings in docs
        for f, _ in skipped_noise:
            doc_name = Path(f.claim.doc_file).name
            by_doc.setdefault(doc_name, [])

    for doc_name, doc_findings in sorted(by_doc.items()):
        doc_broken = sum(1 for f in doc_findings if f.status == "STALE")
        doc_check = sum(1 for f in doc_findings if f.status == "SUSPECT")
        doc_ok = sum(1 for f in doc_findings if f.status == "OK")
        doc_total = doc_broken + doc_check + doc_ok
        doc_acc = round((doc_ok / max(1, doc_total)) * 100) if doc_total > 0 else 100

        doc_blocks = round(doc_acc / 10)
        doc_bar = "█" * doc_blocks + "░" * (10 - doc_blocks)

        note_icon = " 📝" if any(w in doc_name.lower() for w in ("progress", "security", "notes", "changelog")) else ""
        lines.append(f"| `{doc_name}`{note_icon} | `{doc_bar}` {doc_acc}% | {doc_broken} | {doc_check} | {doc_ok} |")

    lines.append("")
    lines.append("📝 = internal notes or changelog. Drift matters less there than in README and API docs.")
    lines.append("")

    # Details: Verified
    lines.append(f"<details><summary><b>🟢 Verified ({verified_count} claims match the code)</b>: click to expand</summary>")
    lines.append("")
    verified_by_doc: dict[str, list[Finding]] = {}
    for f in verified:
        verified_by_doc.setdefault(Path(f.claim.doc_file).name, []).append(f)

    for doc_name, v_items in sorted(verified_by_doc.items()):
        lines.append(f"**`{doc_name}`**")
        for f in v_items:
            cat = _category_name(f.claim.kind)
            lines.append(f"- {cat}: `{f.claim.text}` (L{f.claim.line})")
        lines.append("")
    lines.append("</details>")
    lines.append("")

    # Details: Skipped
    lines.append(f"<details><summary><b>⚪ Skipped ({skipped_count} fragments that looked like claims but aren't)</b></summary>")
    lines.append("")
    lines.append("Listed for transparency. These were left out of the counts above.")
    lines.append("")
    lines.append("| Where | Text | Why skipped |")
    lines.append("|---|---|---|")
    for f, reason in skipped_noise:
        doc_name = Path(f.claim.doc_file).name
        clean_txt = f.claim.text.replace("|", "\\|")
        lines.append(f"| `{doc_name}` L{f.claim.line} | `{clean_txt}` | {reason} |")
    lines.append("")
    lines.append("</details>")
    lines.append("")

    lines.append("---")
    lines.append(
        "**How to read this:** 🔴 broken = the docs mention something the code doesn't have · 🟡 check = near-match, probably a rename · 🟢 verified = confirmed in the code. File locations like `README.md` L94 are clickable in most editors."
    )

    return "\n".join(lines)


def _category_name(kind: str) -> str:
    mapping = {
        "route": "Endpoint",
        "port": "Port",
        "env_var": "Environment variable",
        "npm_script": "npm script",
        "dependency": "Dependency",
        "engine": "Node engine",
    }
    return mapping.get(kind, kind.replace("_", " ").title())