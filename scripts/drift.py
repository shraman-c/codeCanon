#!/usr/bin/env python3
"""docs-drift-detector CLI entrypoint (Member A, Stage 3).

Usage:
    python scripts/drift.py scan <repo> [--no-llm] [--no-images] [--config <file.json>]

Pipeline order: detect -> extract (facts, text claims, image claims) ->
match -> judge -> patch -> report.

Modules owned by teammates (match, extract_images, report, vision) are
imported defensively: when they are not on disk yet the CLI degrades to a
deterministic fallback so the pipeline still runs end to end.

Exit codes: 0 = no STALE findings, 1 = at least one STALE finding,
2 = not a web repo / bad usage.
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import sys
from pathlib import Path

# Ensure UTF-8 stdout/stderr on Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Ensure repository root is in sys.path when run as a script.
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from drift.detect import detect, is_web_project, not_web_error
from drift.extract_docs import scan_file
from drift.extract_env import extract_env
from drift.extract_pkg import extract_pkg
from drift.extract_ports import extract_ports
from drift.extract_routes import extract_routes
from drift.models import Claim, Fact, Finding

# --- Teammate modules (B/C) are optional until they land -------------------
try:
    from drift.match import match_claims as team_match  # type: ignore
except ImportError:
    team_match = None

try:
    from drift import extract_images  # type: ignore
except ImportError:
    extract_images = None

try:
    from drift import report as team_report  # type: ignore
except ImportError:
    team_report = None

try:
    from drift.judge import judge, reset_stats, JUDGE_STATS
except ImportError:
    judge = None
    JUDGE_STATS = {}

try:
    from drift.patch import patch as make_patches, combined_patch
except ImportError:
    make_patches = None
    combined_patch = None

DOC_GLOBS = ("*.md", "*.mdx", "*.txt", "*.rst")
IGNORE_DIRS = {"node_modules", ".next", "dist", "build", ".git", "coverage", ".drift_cache"}

# TRD §6 allow-list: claims that are never drift.
PLACEHOLDER_CLAIM = re.compile(r"^(YOUR_[A-Z_]+|<your-[^>]+>|xxx+|<[^>]+>)$", re.IGNORECASE)
ALLOWED_ENV = {"NODE_ENV", "PORT", "HOME", "PATH", "CI"}
BUILTIN_SCRIPTS = {"start", "test", "install", "ci", "dev", "build", "lint"}


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------
def load_config(path: str | None) -> dict:
    if not path:
        return {}
    cfg_path = Path(path)
    if not cfg_path.is_file():
        raise SystemExit(f"error: config file not found: {path}")
    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"error: invalid JSON in {path}: {exc}")
    if not isinstance(data, dict):
        raise SystemExit(f"error: config must be a JSON object: {path}")
    return data


# ---------------------------------------------------------------------------
# extract
# ---------------------------------------------------------------------------
def collect_facts(repo: Path) -> list[Fact]:
    facts: list[Fact] = []
    facts.extend(extract_pkg(repo))
    facts.extend(extract_env(repo))
    facts.extend(extract_routes(repo))
    facts.extend(extract_ports(repo))
    return facts


def collect_doc_files(repo: Path) -> list[Path]:
    files: list[Path] = []
    for pattern in DOC_GLOBS:
        for path in repo.rglob(pattern):
            if not path.is_file():
                continue
            if any(part in IGNORE_DIRS or part.startswith(".") for part in path.relative_to(repo).parts):
                continue
            files.append(path)
    return sorted(set(files))


def collect_text_claims(repo: Path) -> list[Claim]:
    claims: list[Claim] = []
    for doc in collect_doc_files(repo):
        claims.extend(scan_file(doc))
    return claims


def collect_image_claims(repo: Path, docs: list[Path]) -> list[Claim]:
    """Image claims come from B's extract_images + C's vision modules."""
    if extract_images is None:
        return []
    try:
        builder = getattr(extract_images, "extract_image_claims", None) or getattr(
            extract_images, "collect_image_claims", None
        )
        if builder is None:
            return []
        return list(builder(repo, docs))
    except Exception as exc:  # pragma: no cover - defensive
        print(f"warning: image claim extraction failed ({exc}); continuing with text claims only")
        return []


# ---------------------------------------------------------------------------
# match (fallback when B's match.py is unavailable)
# ---------------------------------------------------------------------------
def _norm_path(path: str) -> str:
    path = path.strip().rstrip("/")
    path = re.sub(r"\{(\w+)\}", r":\1", path)
    path = re.sub(r"\[(\w+)\]", r":\1", path)
    return path.lower()


def _script_name_from_claim(text: str) -> str:
    parts = text.strip().split()
    if not parts:
        return ""
    if "run" in parts:
        idx = parts.index("run")
        return parts[idx + 1] if idx + 1 < len(parts) else parts[-1]
    return parts[-1]


def _port_from_claim(text: str) -> str | None:
    m = re.search(r"(\d{2,5})", text)
    if m and 10 <= int(m.group(1)) <= 65535:
        return m.group(1)
    return None


def _route_from_claim(text: str) -> tuple[str | None, str | None]:
    """Return (method, path) parsed out of a route claim."""
    def _clean(p: str) -> str:
        # Docs often wrap paths in backticks/quotes; normalise them away
        # (TRD §6: comparisons normalised for case, quotes, trailing slash).
        return p.strip().strip("`'\"").rstrip("/")

    m = re.match(r"(?i)^(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+(\S+)$", text.strip())
    if m:
        return m.group(1).upper(), _clean(m.group(2))
    m = re.match(r"(?i)^curl\s+(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+(\S+)$", text.strip())
    if m:
        return m.group(1).upper(), _clean(m.group(2))
    m = re.match(r"(?i)^fetch\(['\"]([^'\"]+)['\"]\)$", text.strip())
    if m:
        return None, _clean(m.group(1))
    if text.strip().startswith("/"):
        return None, _clean(text)
    return None, None


def _finding(claim: Claim, status: str, reason: str, evidence: list[Fact], confidence: float) -> Finding:
    return Finding(
        claim=claim,
        status=status,
        reason=reason,
        evidence=evidence,
        confidence=confidence,
        source="deterministic",
    )


def fallback_match(facts: list[Fact], claims: list[Claim]) -> list[Finding]:
    """Deterministic per-kind matcher used until drift/match.py lands (Member B).

    Rules follow TRD §6: exact → OK, fuzzy/similar → SUSPECT, absent → STALE,
    allow-listed claims are never flagged.
    """
    findings: list[Finding] = []
    by_kind: dict[str, list[Fact]] = {}
    for f in facts:
        by_kind.setdefault(f.kind, []).append(f)

    for claim in claims:
        text = claim.text.strip()

        # --- allow-list: never drift -------------------------------------
        if PLACEHOLDER_CLAIM.match(text):
            continue

        candidates = by_kind.get(claim.kind, [])

        if claim.kind == "npm_script":
            name = _script_name_from_claim(text)
            if not name:
                continue
            exact = [f for f in candidates if f.name == name]
            if exact:
                findings.append(_finding(claim, "OK", f"script `{name}` exists in package.json", exact, 1.0))
                continue
            close = [
                f
                for f in candidates
                if difflib.SequenceMatcher(None, name, f.name).ratio() >= 0.8
            ]
            if close:
                findings.append(
                    _finding(claim, "SUSPECT", f"similar script exists: `{close[0].name}`", close, 0.6)
                )
            elif name in BUILTIN_SCRIPTS:
                findings.append(_finding(claim, "OK", "built-in npm script", [], 0.9))
            else:
                findings.append(_finding(claim, "STALE", f"no script named `{name}` in package.json", candidates, 0.9))

        elif claim.kind == "env_var":
            name = text.split("=", 1)[0].strip()
            if PLACEHOLDER_CLAIM.match(name):
                continue
            if name in ALLOWED_ENV:
                continue
            exact = [f for f in candidates if f.name == name]
            if exact:
                findings.append(_finding(claim, "OK", f"env var {name} present in code", exact, 1.0))
                continue
            close = [f for f in candidates if difflib.SequenceMatcher(None, name, f.name).ratio() >= 0.8]
            if close:
                findings.append(
                    _finding(claim, "SUSPECT", f"similar env var exists: {close[0].name}", close, 0.6)
                )
            else:
                findings.append(_finding(claim, "STALE", f"env var {name} not found in code", candidates, 0.9))

        elif claim.kind == "route":
            method, path = _route_from_claim(text)
            if not path:
                continue
            target = _norm_path(path)
            path_matches = [f for f in candidates if _norm_path(f.name) == target]
            if path_matches:
                if method is None:
                    findings.append(
                        _finding(claim, "OK", f"route {path} exists in code", path_matches, 1.0)
                    )
                else:
                    method_matches = [
                        f for f in path_matches if method in [m.strip().upper() for m in f.detail.split(",")]
                    ]
                    if method_matches:
                        findings.append(
                            _finding(claim, "OK", f"{method} {path} exists in code", method_matches, 1.0)
                        )
                    else:
                        findings.append(
                            _finding(
                                claim,
                                "SUSPECT",
                                f"route {path} exists but not with method {method}",
                                path_matches,
                                0.6,
                            )
                        )
                continue
            close = [
                f
                for f in candidates
                if difflib.SequenceMatcher(None, target, _norm_path(f.name)).ratio() >= 0.8
            ]
            if close:
                findings.append(
                    _finding(claim, "SUSPECT", f"similar route exists: {close[0].name}", close, 0.6)
                )
            else:
                findings.append(_finding(claim, "STALE", f"route {path} not found in code", candidates, 0.9))

        elif claim.kind == "port":
            port = _port_from_claim(text)
            if port is None:
                continue
            hits = [f for f in candidates if port in f.detail]
            if hits:
                findings.append(_finding(claim, "OK", f"port {port} found in code", hits, 1.0))
            else:
                findings.append(_finding(claim, "STALE", f"port {port} not found in code", candidates, 0.9))

        elif claim.kind == "engine":
            m = re.search(r"(\d+(?:\.\d+)*)", text)
            if not m:
                continue
            docs_version = m.group(1)
            docs_major = int(docs_version.split(".")[0])
            if not candidates:
                findings.append(_finding(claim, "OK", "no engine constraint in repo", [], 0.9))
                continue
            min_majors = []
            for f in candidates:
                nums = re.findall(r"\d+", f.detail)
                if nums:
                    min_majors.append(int(nums[0]))
            if min_majors and docs_major >= max(min_majors):
                findings.append(
                    _finding(claim, "OK", f"node {docs_version} satisfies engines ({candidates[0].detail})", candidates, 1.0)
                )
            else:
                findings.append(
                    _finding(
                        claim,
                        "SUSPECT",
                        f"repo requires {candidates[0].detail}, docs say {docs_version}",
                        candidates,
                        0.6,
                    )
                )

        elif claim.kind == "dependency":
            exact = [f for f in candidates if f.name == text or f.name in text]
            if exact:
                findings.append(_finding(claim, "OK", f"dependency {text} present", exact, 1.0))
            else:
                findings.append(_finding(claim, "STALE", f"dependency {text} not in package.json", candidates, 0.9))

        else:
            # Unknown claim kinds (code_sample etc.) go to the judge as SUSPECT.
            findings.append(
                _finding(claim, "SUSPECT", "no deterministic rule for this claim kind", candidates, 0.5)
            )

    return findings


# ---------------------------------------------------------------------------
# report (fallback when B's report.py is unavailable)
# ---------------------------------------------------------------------------
def _model_info(no_llm: bool, model_override: str | None) -> dict:
    import os

    base_url = os.environ.get("DRIFT_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
    model_id = model_override or os.environ.get("DRIFT_MODEL", "gemma-4-31b-it")
    mode = "local" if ("localhost" in base_url or "127.0.0.1" in base_url) else "api"
    return {
        "id": model_id if not no_llm else f"{model_id} (disabled: --no-llm)",
        "mode": mode,
        "config": {"threshold": 0.6},
    }


def write_report(
    repo: Path,
    proj_kind: str,
    facts: list[Fact],
    claims: list[Claim],
    findings: list[Finding],
    model_info: dict,
    output: Path,
) -> None:
    """Write drift-report.json (+ .md) using team report.py when available."""
    if team_report is not None and hasattr(team_report, "write_report"):
        team_report.write_report(
            repo_path=str(repo),
            kind=proj_kind,
            mode="scan",
            facts=facts,
            claims=claims,
            findings=findings,
            model=model_info,
            output=output,
        )
        return

    try:
        from drift.llm import get_token_stats
        tok_stats = get_token_stats()
    except Exception:
        tok_stats = {"calls": 0, "cache_hits": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "saved_tokens": 0}

    payload = {
        "metadata": {
            "repo_path": str(repo),
            "kind": proj_kind,
            "mode": "scan",
            "diff": None,
            "ignored_paths": sorted(IGNORE_DIRS),
            "stats": {
                "facts": len(facts),
                "claims": len(claims),
                "findings": len(findings),
                "stale": sum(1 for f in findings if f.status == "STALE"),
                "suspect": sum(1 for f in findings if f.status == "SUSPECT"),
                "ok": sum(1 for f in findings if f.status == "OK"),
                "tokens": tok_stats,
            },
        },
        "facts": [f.__dict__ for f in facts],
        # Schema requires source ∈ {text, image}; extract_docs currently emits
        # "code" for fenced blocks (models.py contract says text|image), so the
        # fallback writer normalises it here. See progress.md, item for Member B.
        "claims": [
            {**c.to_dict(), "source": "image" if c.source == "image" else "text"}
            for c in claims
        ],
        "findings": [
            {
                **f.to_dict(),
                "claim": {
                    **f.claim.to_dict(),
                    "source": "image" if f.claim.source == "image" else "text",
                },
            }
            for f in findings
        ],
        "model": model_info,
    }
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    md = [f"# drift-report — {repo.name}", ""]
    md.append(f"Project type: `{proj_kind}`  ")
    md.append(f"Findings: **{len(findings)}** (STALE {payload['metadata']['stats']['stale']}, "
              f"SUSPECT {payload['metadata']['stats']['suspect']}, OK {payload['metadata']['stats']['ok']})")
    md.append(f"Model: `{model_info['id']}` ({model_info['mode']})")
    md.append("")
    md.append("| Status | Doc | Line | Claim | Reason |")
    md.append("|---|---|---|---|---|")
    for f in findings:
        claim_txt = f.claim.text.replace("|", "\\|")
        reason = f.reason.replace("|", "\\|")
        md.append(f"| {f.status} | {Path(f.claim.doc_file).name} | {f.claim.line} | {claim_txt} | {reason} |")
    md.append("")
    md.append("## Patches")
    any_patch = False
    for f in findings:
        if f.patch:
            any_patch = True
            md.append(f"\n### {Path(f.claim.doc_file).name}:{f.claim.line} — {f.claim.text}\n")
            md.append("```diff")
            md.append(f.patch.rstrip())
            md.append("```")
    if not any_patch:
        md.append("\n_No patches generated._")
    output.with_suffix(".md").write_text("\n".join(md) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# scan command
# ---------------------------------------------------------------------------
def _do_run_scan(repo: Path, args: argparse.Namespace, cfg: dict) -> int:
    no_llm = bool(args.no_llm or cfg.get("no_llm", False))
    no_images = bool(args.no_images or cfg.get("no_images", False)) or no_llm  # --no-llm also skips images
    model_override = getattr(args, "model", None) or cfg.get("model")
    if model_override:
        os.environ["DRIFT_MODEL"] = model_override
    try:
        from drift.llm import reset_token_stats
        reset_token_stats()
    except Exception:
        pass
    output = Path(cfg.get("output", "drift-report.json")).resolve()

    if not repo.is_dir():
        print(f"error: not a directory: {repo}", file=sys.stderr)
        return 2

    # 1. detect -------------------------------------------------------------
    if not is_web_project(repo):
        print(not_web_error(repo))
        return 2
    proj_kind = detect(repo)
    print(f"Project type: {proj_kind}")

    # 2. extract ------------------------------------------------------------
    facts = collect_facts(repo)
    print(f"Facts: {len(facts)}")

    doc_files = collect_doc_files(repo)
    claims = collect_text_claims(repo)
    print(f"Docs scanned: {len(doc_files)}  text claims: {len(claims)}")

    if not no_images:
        image_claims = collect_image_claims(repo, doc_files)
        if image_claims:
            claims.extend(image_claims)
            print(f"image claims: {len(image_claims)}")
        elif extract_images is None:
            print("image claims: skipped (drift/extract_images.py not available yet)")
    else:
        print("image claims: skipped (--no-images)" if not no_llm else "image claims: skipped (--no-llm)")

    # 3. match --------------------------------------------------------------
    if team_match is not None:
        findings = team_match(claims, facts)
        matcher_name = "drift.match"
    else:
        findings = fallback_match(facts, claims)
        matcher_name = "built-in fallback (drift/match.py not available yet)"
    stale = sum(1 for f in findings if f.status == "STALE")
    suspect = sum(1 for f in findings if f.status == "SUSPECT")
    print(f"Findings: {len(findings)} (STALE {stale}, SUSPECT {suspect})  matcher: {matcher_name}")

    # 4. judge --------------------------------------------------------------
    if not no_llm and judge is not None:
        try:
            reset_stats()
        except Exception:
            pass
        findings = judge(findings)
        stale = sum(1 for f in findings if f.status == "STALE")
        suspect = sum(1 for f in findings if f.status == "SUSPECT")
        print(f"After judge: STALE {stale}, SUSPECT {suspect}  stats: {JUDGE_STATS}")
    elif not no_llm:
        print("judge: skipped (drift/judge.py not available yet)")
    else:
        print("judge: skipped (--no-llm)")

    # 5. patch --------------------------------------------------------------
    if make_patches is not None:
        findings = make_patches(findings, repo=repo)
        patch_count = sum(1 for f in findings if f.patch)
        print(f"Patches generated: {patch_count}")

    # 6. report -------------------------------------------------------------
    model_info = _model_info(no_llm, model_override)
    write_report(repo, proj_kind, facts, claims, findings, model_info, output)
    print(f"Report written: {output} (+ {output.with_suffix('.md').name})")

    if make_patches is not None and combined_patch is not None:
        diff = combined_patch(findings, repo=repo)
        if diff:
            diff_path = output.with_suffix(".patch")
            diff_path.write_text(diff, encoding="utf-8")
            print(f"Unified diff written: {diff_path}")
    # 6.5 token usage -------------------------------------------------------
    try:
        from drift.llm import get_token_stats
        token_stats = get_token_stats()
    except Exception:
        token_stats = {"calls": 0, "cache_hits": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "saved_tokens": 0}

    print("\n" + "=" * 90)
    print("TOKEN & RESOURCE USAGE:")
    print(f"  Model:              {model_info['id']} ({model_info['mode']})")
    print(f"  LLM Calls:          {token_stats.get('calls', 0)} (Cache hits: {token_stats.get('cache_hits', 0)})")
    print(f"  Prompt Tokens:      {token_stats.get('prompt_tokens', 0):,}")
    print(f"  Completion Tokens:  {token_stats.get('completion_tokens', 0):,}")
    print(f"  Total Tokens Used:  {token_stats.get('total_tokens', 0):,}")
    if token_stats.get("saved_tokens", 0) > 0:
        print(f"  Tokens Saved (Hit): {token_stats.get('saved_tokens', 0):,}")
    print("=" * 90)

    # 7. summary ------------------------------------------------------------
    md_path = output.with_suffix(".md")
    if md_path.exists():
        print("\n" + "=" * 90)
        print(md_path.read_text(encoding="utf-8").strip())
        print("=" * 90)
    else:
        print("\n" + "=" * 90)
        print(f"{'STATUS':<9} {'DOC':<24} {'LINE':<6} {'CLAIM'}")
        print("-" * 90)
        for f in findings:
            if f.status == "OK":
                continue
            doc = Path(f.claim.doc_file).name
            claim_txt = f.claim.text if len(f.claim.text) <= 55 else f.claim.text[:52] + "..."
            print(f"{f.status:<9} {doc:<24} {f.claim.line:<6} {claim_txt}")
            print(f"          -> {f.reason}")
        print("=" * 90)

    # Determine exit code based on actual broken problems reported
    real_broken = stale
    if output.exists():
        try:
            report_data = json.loads(output.read_text(encoding="utf-8"))
            real_broken = report_data.get("summary", {}).get("broken_count", stale)
        except Exception:
            pass

    return 1 if real_broken > 0 else 0


def run_scan(args: argparse.Namespace, cfg: dict) -> int:
    repo_arg = args.repo
    is_url = repo_arg.startswith(("http://", "https://", "git@"))

    temp_dir_obj = None
    if is_url:
        import tempfile
        import subprocess
        temp_dir_obj = tempfile.TemporaryDirectory(prefix="drift_")
        repo_name = repo_arg.rstrip("/").split("/")[-1]
        if repo_name.endswith(".git"):
            repo_name = repo_name[:-4]
        clone_dir = Path(temp_dir_obj.name) / repo_name
        print(f"Cloning {repo_arg} into temporary directory...")
        res = subprocess.run(["git", "clone", "--depth", "1", repo_arg, str(clone_dir)], capture_output=True, text=True)
        if res.returncode != 0:
            print(f"error: failed to clone {repo_arg}:\n{res.stderr}", file=sys.stderr)
            temp_dir_obj.cleanup()
            return 2
        repo = clone_dir.resolve()
    else:
        repo = Path(repo_arg).expanduser().resolve()

    try:
        return _do_run_scan(repo, args, cfg)
    finally:
        if temp_dir_obj is not None:
            temp_dir_obj.cleanup()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="drift.py",
        description="docs-drift-detector: find documentation drift in JS/TS web repos.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="scan a repo for documentation drift")
    scan.add_argument("repo", help="path to the web repository to scan")
    scan.add_argument("--no-llm", action="store_true",
                      help="deterministic only: skips the Gemma 4 judge AND image claims")
    scan.add_argument("--no-images", action="store_true",
                      help="skip image/screenshot claim extraction (text claims only)")
    scan.add_argument("--model", metavar="NAME",
                      help="Gemma 4 model override (e.g. gemma-4-31b-it, gemma-4-26b-a4b-it, gemma4:e4b)")
    scan.add_argument("--config", metavar="FILE",
                      help="optional JSON config: {\"no_llm\": bool, \"no_images\": bool, "
                           "\"model\": str, \"output\": str}; CLI flags win")

    args = parser.parse_args(argv)
    cfg = load_config(args.config)

    if args.command == "scan":
        return run_scan(args, cfg)
    return 2


if __name__ == "__main__":
    sys.exit(main())
