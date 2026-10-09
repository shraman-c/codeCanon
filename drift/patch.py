from __future__ import annotations

import os
import re
import difflib
import subprocess
from pathlib import Path
from typing import Optional

from .models import Finding, Fact, Claim


def get_deterministic_correction(claim_text: str, claim_kind: str, evidence: list[Fact]) -> Optional[str]:
    """Find deterministic closest name from evidence facts.
    
    Order/rules:
    - difflib SequenceMatcher >= 0.8
    - keep package-manager prefix for scripts
    - env prefix-aware for env vars
    - keep HTTP method for routes
    """
    if not evidence or not claim_text:
        return None

    # 1. Route: keep HTTP method
    http_methods = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS")
    parts = claim_text.strip().split(" ", 1)
    if len(parts) == 2 and parts[0].upper() in http_methods:
        method = parts[0].upper()
        route_path = parts[1].strip()
        best_match = None
        best_ratio = 0.0
        for fact in evidence:
            fact_path = fact.name.strip().split(" ", 1)[-1]
            ratio = difflib.SequenceMatcher(None, route_path, fact_path).ratio()
            if ratio >= 0.8 and ratio > best_ratio:
                best_ratio = ratio
                best_match = f"{method} {fact_path}"
        if best_match:
            return best_match

    # 2. Package manager scripts: keep prefix
    pkg_prefixes = (
        "npm run ", "pnpm run ", "yarn run ", "bun run ",
        "npm ", "pnpm ", "yarn ", "bun "
    )
    for pfx in pkg_prefixes:
        if claim_text.startswith(pfx):
            script_part = claim_text[len(pfx):].strip()
            best_match = None
            best_ratio = 0.0
            for fact in evidence:
                ratio = difflib.SequenceMatcher(None, script_part, fact.name.strip()).ratio()
                if ratio >= 0.8 and ratio > best_ratio:
                    best_ratio = ratio
                    best_match = f"{pfx}{fact.name.strip()}"
            if best_match:
                return best_match

    # 3. Environment variables: prefix-aware
    env_code_prefixes = ("process.env.", "import.meta.env.")
    code_pfx = ""
    clean_claim = claim_text.strip()
    for cp in env_code_prefixes:
        if clean_claim.startswith(cp):
            code_pfx = cp
            clean_claim = clean_claim[len(cp):].strip()
            break

    # Strip client/framework prefixes to find root base name
    var_base = re.sub(r"^(NEXT_PUBLIC_|VITE_|REACT_APP_)", "", clean_claim)
    for fact in evidence:
        fact_name = fact.name.strip()
        fact_base = re.sub(r"^(NEXT_PUBLIC_|VITE_|REACT_APP_)", "", fact_name)
        # If base name matches exactly across prefix difference:
        if var_base == fact_base:
            return f"{code_pfx}{fact_name}"
        # Or if full token or base name matches with >= 0.8 ratio:
        ratio = difflib.SequenceMatcher(None, clean_claim, fact_name).ratio()
        if ratio >= 0.8:
            return f"{code_pfx}{fact_name}"
        ratio_base = difflib.SequenceMatcher(None, var_base, fact_base).ratio()
        if ratio_base >= 0.8:
            return f"{code_pfx}{fact_name}"

    # 4. General closest name match >= 0.8
    best_match = None
    best_ratio = 0.0
    for fact in evidence:
        ratio = difflib.SequenceMatcher(None, claim_text.strip(), fact.name.strip()).ratio()
        if ratio >= 0.8 and ratio > best_ratio:
            best_ratio = ratio
            best_match = fact.name.strip()

    return best_match


def patch(findings: list[Finding], repo: Path) -> list[Finding]:
    """Generate and verify unified diff patches for STALE findings without modifying repo files."""
    repo_path = Path(repo).resolve()

    for finding in findings:
        claim = finding.claim

        # Handle image findings
        if claim.source == "image":
            finding.patch = None
            quote = (
                getattr(claim, "extracted_quote", None)
                or getattr(claim, "extracted_text", None)
                or claim.text
            )
            fact_name = finding.evidence[0].name if finding.evidence else "code"
            setattr(
                finding,
                "note",
                f"Replace image {claim.image_path}: shows '{quote}' but code has '{fact_name}'",
            )
            continue

        # Only STALE text findings are patched
        if finding.status.upper() != "STALE":
            finding.patch = None
            continue

        # Correction determination order:
        # 1. Deterministic closest name from evidence
        # 2. LLM corrected_text
        # 3. Else patch=None, needs_review=True
        replacement = get_deterministic_correction(claim.text, claim.kind, finding.evidence)
        if not replacement:
            llm_corrected = getattr(finding, "corrected_text", None)
            if llm_corrected and str(llm_corrected).strip():
                replacement = str(llm_corrected).strip()

        if not replacement:
            finding.patch = None
            setattr(finding, "needs_review", True)
            continue

        # Target file resolution
        doc_file_rel = Path(claim.doc_file)
        if doc_file_rel.is_absolute():
            try:
                doc_path = doc_file_rel
                doc_file_rel = doc_path.relative_to(repo_path)
            except ValueError:
                doc_path = doc_file_rel
        else:
            doc_path = repo_path / doc_file_rel

        if not doc_path.is_file():
            finding.patch = None
            setattr(finding, "needs_review", True)
            setattr(finding, "note", f"Doc file not found: {claim.doc_file}")
            continue

        # Read file preserving line breaks (CRLF/LF)
        try:
            with doc_path.open("r", encoding="utf-8", newline="") as f:
                raw_text = f.read()
        except Exception as e:
            finding.patch = None
            setattr(finding, "needs_review", True)
            setattr(finding, "note", f"Failed to read doc file: {e}")
            continue

        # Split lines for diffing
        raw_lines = [l + "\n" for l in raw_text.splitlines()]
        line_idx = claim.line - 1

        if line_idx < 0 or line_idx >= len(raw_lines):
            finding.patch = None
            setattr(finding, "needs_review", True)
            setattr(finding, "note", f"claim.line {claim.line} out of range")
            continue

        orig_line = raw_lines[line_idx]
        target_span = claim.text

        # If claim.text doesn't appear on line, check stripped or without prefix
        if target_span not in orig_line:
            parts = claim.text.split(" ", 1)
            if len(parts) == 2 and parts[1] in orig_line:
                target_span = parts[1]
                if replacement.startswith(parts[0] + " "):
                    replacement = replacement[len(parts[0]) + 1:]

        # Must occur exactly once on claim.line or no patch
        count = orig_line.count(target_span)
        if count != 1:
            finding.patch = None
            setattr(finding, "needs_review", True)
            setattr(
                finding,
                "note",
                f"Claim span '{target_span}' occurs {count} times on line {claim.line}",
            )
            continue

        new_line = orig_line.replace(target_span, replacement, 1)
        if new_line == orig_line:
            finding.patch = None
            continue

        new_lines = list(raw_lines)
        new_lines[line_idx] = new_line

        rel_posix = doc_file_rel.as_posix()
        diff_lines = list(
            difflib.unified_diff(
                raw_lines,
                new_lines,
                fromfile=f"a/{rel_posix}",
                tofile=f"b/{rel_posix}",
            )
        )

        patch_str = "".join(diff_lines)
        if not patch_str:
            finding.patch = None
            continue

        # Verify patch with git apply --check (never modifying repo files)
        try:
            proc = subprocess.run(
                ["git", "apply", "--check", "-"],
                input=patch_str,
                text=True,
                cwd=repo_path,
                capture_output=True,
            )
            if proc.returncode == 0:
                finding.patch = patch_str
                setattr(finding, "needs_review", False)
                setattr(finding, "_patch_repo", repo_path)
                setattr(finding, "_target_file", rel_posix)
                setattr(finding, "_line_idx", line_idx)
                setattr(finding, "_target_span", target_span)
                setattr(finding, "_replacement", replacement)
            else:
                finding.patch = None
                setattr(finding, "needs_review", True)
                setattr(
                    finding,
                    "note",
                    f"git apply --check failed: {proc.stderr.strip()}",
                )
        except Exception as e:
            finding.patch = None
            setattr(finding, "needs_review", True)
            setattr(finding, "note", f"git apply execution error: {e}")

    return findings


def combined_patch(findings: list[Finding], repo: Optional[Path] = None) -> str:
    """Combine patches from all findings into a single unified diff.
    
    If multiple patches touch the same file, applies all replacements cleanly
    to the source file to produce a conflict-free unified diff.
    """
    patched_findings = [f for f in findings if getattr(f, "patch", None)]
    if not patched_findings:
        return ""

    # Group by file
    by_file: dict[str, list[Finding]] = {}
    for f in patched_findings:
        target_file = getattr(f, "_target_file", None) or Path(f.claim.doc_file).as_posix()
        by_file.setdefault(target_file, []).append(f)

    combined_diff_parts: list[str] = []

    for target_file, file_findings in by_file.items():
        if len(file_findings) == 1:
            combined_diff_parts.append(file_findings[0].patch)
            continue

        # Multiple patches touch the same file: merge into a single diff
        rep = repo or getattr(file_findings[0], "_patch_repo", None)
        if rep is not None:
            doc_path = Path(rep) / target_file
            if doc_path.is_file():
                try:
                    with doc_path.open("r", encoding="utf-8", newline="") as fp:
                        raw_lines = [l + "\n" for l in fp.read().splitlines()]
                    new_lines = list(raw_lines)
                    for f in file_findings:
                        line_idx = getattr(f, "_line_idx", f.claim.line - 1)
                        span = getattr(f, "_target_span", f.claim.text)
                        repl = getattr(f, "_replacement", None) or getattr(f, "corrected_text", None)
                        if 0 <= line_idx < len(new_lines) and repl and span:
                            new_lines[line_idx] = new_lines[line_idx].replace(span, repl, 1)

                    merged_diff = "".join(
                        difflib.unified_diff(
                            raw_lines,
                            new_lines,
                            fromfile=f"a/{target_file}",
                            tofile=f"b/{target_file}",
                        )
                    )
                    combined_diff_parts.append(merged_diff)
                    continue
                except Exception:
                    pass

        # Fallback: concatenate
        for f in file_findings:
            combined_diff_parts.append(f.patch)

    return "".join(combined_diff_parts)

