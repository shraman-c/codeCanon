import sys
import json
import argparse
import subprocess
from pathlib import Path
from typing import Optional

# Ensure repository root is in sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from drift.detect import detect
from drift.extract_pkg import extract_pkg
from drift.extract_env import extract_env
from drift.extract_docs import scan_file, extract_claims_from_files
from drift.models import Finding, Fact, Claim
from drift.judge import judge, JUDGE_STATS, reset_stats
from drift.patch import patch, combined_patch

# Optional extractors
try:
    from drift.extract_routes import extract_routes
except ImportError:
    extract_routes = None

try:
    from drift.extract_ports import extract_ports
except ImportError:
    extract_ports = None

# Optional matcher from teammate B
try:
    from drift.match import match as b_match
except ImportError:
    b_match = None


def fallback_match(facts: list[Fact], claims: list[Claim]) -> list[Finding]:
    """Fallback matcher when B's match.py is not yet available."""
    findings: list[Finding] = []
    facts_by_kind: dict[str, list[Fact]] = {}
    for f in facts:
        facts_by_kind.setdefault(f.kind, []).append(f)

    for c in claims:
        candidates = facts_by_kind.get(c.kind, [])
        # Exact match
        exact = [f for f in candidates if f.name == c.text or f.name in c.text]
        if exact:
            findings.append(
                Finding(
                    claim=c,
                    status="OK",
                    reason=f"Matches code fact: {exact[0].name}",
                    evidence=exact,
                    confidence=1.0,
                    source="deterministic",
                )
            )
        else:
            findings.append(
                Finding(
                    claim=c,
                    status="SUSPECT",
                    reason="Possible documentation drift; suspect discrepancy with codebase facts.",
                    evidence=candidates,
                    confidence=0.5,
                    source="deterministic",
                )
            )
    return findings


def run_pipeline(repo_path: Path, no_llm: bool = False) -> None:
    repo = repo_path.resolve()
    print(f"\n=== Dev Pipeline Run: {repo.name} ===")

    # 1. Detect
    proj_type = detect(repo)
    print(f"Project Type: {proj_type}")

    # 2. Extract facts
    facts: list[Fact] = []
    facts.extend(extract_pkg(repo))
    facts.extend(extract_env(repo))
    if extract_routes is not None:
        facts.extend(extract_routes(repo))
    if extract_ports is not None:
        facts.extend(extract_ports(repo))
    print(f"Extracted Facts: {len(facts)}")

    # 3. Extract doc claims
    doc_files = []
    for ext in ("*.md", "*.mdx", "*.txt"):
        doc_files.extend(repo.rglob(ext))
    # Filter out node_modules, .git, etc.
    doc_files = [
        f for f in doc_files
        if not any(part.startswith(".") or part in ("node_modules", "dist", "build") for part in f.parts)
    ]
    claims: list[Claim] = []
    for df in doc_files:
        claims.extend(scan_file(df))
    print(f"Extracted Doc Claims: {len(claims)}")

    # 4. Match
    if b_match is not None:
        findings = b_match(facts, claims)
    else:
        findings = fallback_match(facts, claims)
    print(f"Initial Findings: {len(findings)} (Suspect: {sum(1 for f in findings if f.status == 'SUSPECT')})")

    # 5. Judge
    if not no_llm:
        print("\nRunning LLM Judge (Gemma 4)...")
        reset_stats()
        findings = judge(findings)
        print(f"Judge Stats: {JUDGE_STATS}")
    else:
        print("\nSkipping LLM Judge (--no-llm mode)")

    # 6. Patch
    print("\nRunning Patch Generator...")
    findings = patch(findings, repo=repo)
    comp_patch = combined_patch(findings, repo=repo)

    # 7. Print Table
    print("\n" + "=" * 105)
    header = f"{'Claim':<28} | {'Doc:Line':<18} | {'Status':<8} | {'Source':<13} | {'Conf':<5} | {'Patch?'}"
    print(header)
    print("-" * 105)
    for f in findings:
        claim_str = (f.claim.text[:25] + "...") if len(f.claim.text) > 28 else f.claim.text
        doc_pos = f"{Path(f.claim.doc_file).name}:{f.claim.line}"
        has_patch = "yes" if f.patch else ("needs_review" if getattr(f, "needs_review", False) else "no")
        row = f"{claim_str:<28} | {doc_pos:<18} | {f.status:<8} | {f.source:<13} | {f.confidence:<5.2f} | {has_patch}"
        print(row)
        if getattr(f, "note", None):
            print(f"  Note: {f.note}")
        if f.status == "STALE" and f.reason:
            print(f"  Reason: {f.reason}")
    print("=" * 105)

    # 8. Combined Patch & Apply Check
    if comp_patch:
        print("\n--- Combined Unified Diff ---")
        print(comp_patch)
        check_proc = subprocess.run(
            ["git", "apply", "--check", "-"],
            input=comp_patch,
            text=True,
            cwd=repo,
            capture_output=True,
        )
        if check_proc.returncode == 0:
            print("Git Apply Check: PASS (Patch applies cleanly)")
        else:
            print(f"Git Apply Check: FAIL ({check_proc.stderr.strip()})")
    else:
        print("\nCombined Unified Diff: None (No patches generated)")


def main():
    parser = argparse.ArgumentParser(description="codeCanon Dev Pipeline Entrypoint")
    parser.add_argument("repo", type=str, help="Path to repository")
    parser.add_argument("--no-llm", action="store_true", help="Skip LLM judging")
    args = parser.parse_args()

    run_pipeline(Path(args.repo), no_llm=args.no_llm)


if __name__ == "__main__":
    main()
