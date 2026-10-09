#!/usr/bin/env python3
"""benchmark/run_bench.py — planted-drift benchmark (Member A, Stage 3).

Usage:
    python benchmark/run_bench.py --model gemma-4-31b-it [--fixture NAME] [--llm]

For each fixture under benchmark/fixtures/ that contains a package.json:
  1. run `scripts/drift.py scan <fixture>` (deterministic `--no-llm` unless --llm)
  2. compare the findings in drift-report.json with benchmark/expected.json
  3. compute text recall / image recall / decoys wrongly flagged / LLM calls
     saved / patch validity / runtime, plus a naive grep baseline
  4. write benchmark/results/<model>.json and print a table
"""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = ROOT / "benchmark" / "fixtures"
EXPECTED_PATH = ROOT / "benchmark" / "expected.json"
RESULTS_DIR = ROOT / "benchmark" / "results"

DOC_EXTS = {".md", ".mdx", ".txt", ".rst"}
IGNORE_DIRS = {"node_modules", ".next", "dist", "build", ".git", "coverage", ".drift_cache"}
HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
JUDGE_BATCH = 5  # TRD §7.2: judge sees up to 5 SUSPECT findings per call


def norm(text: str) -> str:
    """Normalise a claim/expected text for comparison (backticks, quotes, slash)."""
    return text.strip().strip("`'\"").rstrip("/")


def doc_matches(claim_doc: str, expected_doc: str) -> bool:
    doc = claim_doc.replace("\\", "/")
    return doc == expected_doc or doc.endswith("/" + expected_doc)


def load_expected() -> dict:
    if not EXPECTED_PATH.is_file():
        raise SystemExit(f"error: missing ground truth: {EXPECTED_PATH}")
    return json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))


def discover_fixtures(only: str | None) -> list[Path]:
    fixtures = sorted(p for p in FIXTURES_DIR.iterdir() if p.is_dir() and (p / "package.json").is_file())
    if only:
        fixtures = [p for p in fixtures if p.name == only]
        if not fixtures:
            raise SystemExit(f"error: fixture {only!r} not found (or has no package.json)")
    return fixtures


def run_scan(fixture: Path, llm: bool, model: str) -> tuple[dict | None, str, float, int]:
    """Run the CLI on one fixture; return (report, stdout, seconds, exit_code)."""
    with tempfile.TemporaryDirectory() as tmp:
        report_path = Path(tmp) / "drift-report.json"
        cfg_path = Path(tmp) / "cfg.json"
        cfg_path.write_text(json.dumps({"output": str(report_path), "model": model}), encoding="utf-8")

        cmd = [sys.executable, "scripts/drift.py", "scan", str(fixture), "--config", str(cfg_path)]
        if not llm:
            cmd.append("--no-llm")

        started = time.perf_counter()
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        elapsed = time.perf_counter() - started

        stdout = (proc.stdout or "") + (proc.stderr or "")
        report = None
        if report_path.is_file():
            report = json.loads(report_path.read_text(encoding="utf-8"))
        return report, stdout, elapsed, proc.returncode


def find_finding(findings: list[dict], entry: dict) -> dict | None:
    target = norm(entry["text"])
    for f in findings:
        c = f["claim"]
        if c["kind"] != entry["kind"]:
            continue
        if norm(c["text"]) != target:
            continue
        if not doc_matches(c["doc_file"], entry["doc"]):
            continue
        return f
    return None


def score_fixture(report: dict, expected: dict) -> dict:
    findings = report["findings"]
    planted = expected.get("planted", [])
    decoys = expected.get("decoys", [])
    image_planted = expected.get("image_planted", [])
    image_decoys = expected.get("image_decoys", [])

    def flagged(entry: dict) -> bool:
        f = find_finding(findings, entry)
        return f is not None and f["status"] != "OK"

    text_detected = sum(1 for e in planted if flagged(e))
    image_detected = sum(1 for e in image_planted if flagged(e))
    decoys_flagged = sum(1 for e in decoys if flagged(e))
    image_decoys_flagged = sum(1 for e in image_decoys if flagged(e))

    # Unlisted STALE findings (not in planted or decoy lists) — informational.
    listed = {norm(e["text"]) for e in planted + decoys + image_planted + image_decoys}
    unlisted_stale = [
        f["claim"]["text"]
        for f in findings
        if f["status"] == "STALE" and norm(f["claim"]["text"]) not in listed
    ]

    stale_text = [f for f in findings if f["status"] == "STALE" and f["claim"].get("source") != "image"]
    patched = [f for f in stale_text if f.get("patch")]
    needs_review = [f for f in stale_text if not f.get("patch")]

    suspects = sum(1 for f in findings if f["status"] == "SUSPECT")

    return {
        "text_planted": len(planted),
        "text_detected": text_detected,
        "text_recall": (text_detected / len(planted)) if planted else None,
        "image_planted": len(image_planted),
        "image_detected": image_detected,
        "image_recall": (image_detected / len(image_planted)) if image_planted else None,
        "decoys": len(decoys),
        "decoys_wrongly_flagged": decoys_flagged,
        "image_decoys_wrongly_flagged": image_decoys_flagged,
        "findings_total": len(findings),
        "stale": sum(1 for f in findings if f["status"] == "STALE"),
        "suspect": suspects,
        "ok": sum(1 for f in findings if f["status"] == "OK"),
        "unlisted_stale": unlisted_stale,
        "patches_generated": len(patched),
        "patches_needs_review": len(needs_review),
        "patch_validity": (len(patched) / len(stale_text)) if stale_text else None,
        "suspects_at_judge": suspects,
    }


# ---------------------------------------------------------------------------
# naive grep baseline
# ---------------------------------------------------------------------------
def iter_source_texts(fixture: Path):
    """Text of every non-doc file; hidden FILES (.nvmrc, .env.example) are
    included like a real grep would, hidden/ignored DIRECTORIES are not."""
    for path in sorted(fixture.rglob("*")):
        if not path.is_file():
            continue
        parent_parts = path.relative_to(fixture).parts[:-1]
        if any(p in IGNORE_DIRS or p.startswith(".") for p in parent_parts):
            continue
        if path.suffix.lower() in DOC_EXTS:
            continue
        try:
            yield path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue


def grep_token(entry: dict) -> str | None:
    kind, text = entry["kind"], norm(entry["text"])
    if kind == "npm_script":
        return text.split()[-1] if text.split() else None
    if kind == "env_var":
        return text.split("=", 1)[0]
    if kind == "route":
        m = re.match(r"(?i)^fetch\(['\"]([^'\"]+)", text)
        if m:
            return norm(m.group(1))
        parts = text.split(" ", 1)
        if len(parts) == 2 and parts[0].upper() in HTTP_METHODS:
            return norm(parts[1])
        return text
    if kind == "port":
        m = re.search(r"\d{2,5}", text)
        return m.group(0) if m else None
    if kind == "engine":
        m = re.search(r"\d+(?:\.\d+)*", text)
        return m.group(0) if m else None
    return text


def grep_baseline(fixture: Path, expected: dict) -> dict:
    """Naive baseline: flag a doc claim as stale when its token is absent
    from the repo's non-doc files. Recall-focused, no normalisation."""
    source_blob = "\n".join(iter_source_texts(fixture))

    def predicted_stale(entry: dict) -> bool:
        token = grep_token(entry)
        if not token:
            return False
        return token not in source_blob

    planted = expected.get("planted", [])
    decoys = expected.get("decoys", [])
    detected = sum(1 for e in planted if predicted_stale(e))
    flagged = sum(1 for e in decoys if predicted_stale(e))
    return {
        "text_planted": len(planted),
        "text_detected": detected,
        "text_recall": (detected / len(planted)) if planted else None,
        "decoys": len(decoys),
        "decoys_wrongly_flagged": flagged,
    }


# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="docs-drift-detector benchmark against expected.json")
    parser.add_argument("--model", default=None, help="model id to record (default: $DRIFT_MODEL or gemma-4-31b-it)")
    parser.add_argument("--fixture", default=None, help="run a single fixture by name (default: all)")
    parser.add_argument("--llm", action="store_true", help="run with the Gemma 4 judge (default: --no-llm)")
    args = parser.parse_args(argv)

    import os

    model = args.model or os.environ.get("DRIFT_MODEL", "gemma-4-31b-it")
    expected_all = load_expected()
    fixtures = discover_fixtures(args.fixture)
    if not fixtures:
        raise SystemExit("error: no fixtures with a package.json under benchmark/fixtures/")

    per_fixture: dict[str, dict] = {}
    total_runtime = 0.0
    llm_calls_made = 0

    for fixture in fixtures:
        name = fixture.name
        expected = expected_all.get(name, {"planted": [], "decoys": []})
        report, stdout, elapsed, exit_code = run_scan(fixture, llm=args.llm, model=model)
        total_runtime += elapsed

        if report is None:
            per_fixture[name] = {
                "error": f"scan failed (exit {exit_code})",
                "stdout_tail": stdout[-1200:],
                "runtime_s": round(elapsed, 3),
            }
            print(f"[{name}] scan failed (exit {exit_code}) — see stdout_tail in results file")
            continue

        entry = score_fixture(report, expected)
        entry["runtime_s"] = round(elapsed, 3)
        entry["exit_code"] = exit_code
        entry["grep_baseline"] = grep_baseline(fixture, expected)

        calls = re.search(r"'calls_made':\s*(\d+)", stdout)
        if calls:
            llm_calls_made += int(calls.group(1))
        entry["llm_calls_saved"] = 0 if args.llm else math.ceil(entry["suspects_at_judge"] / JUDGE_BATCH)

        per_fixture[name] = entry

        def fmt_pct(v):
            return "n/a" if v is None else f"{v * 100:.0f}%"

        pv = entry["patch_validity"]
        print(
            f"[{name}] text recall {fmt_pct(entry['text_recall'])} "
            f"({entry['text_detected']}/{entry['text_planted']}), "
            f"image recall {fmt_pct(entry['image_recall'])}, "
            f"decoys flagged {entry['decoys_wrongly_flagged']}/{entry['decoys']}, "
            f"patches {entry['patches_generated']} (validity {'n/a' if pv is None else f'{pv * 100:.0f}%'}), "
            f"grep baseline recall {fmt_pct(entry['grep_baseline']['text_recall'])} "
            f"with {entry['grep_baseline']['decoys_wrongly_flagged']} decoys flagged, "
            f"runtime {entry['runtime_s']}s"
        )

    # ---- aggregate --------------------------------------------------------
    scored = {k: v for k, v in per_fixture.items() if "error" not in v}
    agg = {
        "text_planted": sum(v["text_planted"] for v in scored.values()),
        "text_detected": sum(v["text_detected"] for v in scored.values()),
        "decoys": sum(v["decoys"] for v in scored.values()),
        "decoys_wrongly_flagged": sum(v["decoys_wrongly_flagged"] for v in scored.values()),
        "image_planted": sum(v["image_planted"] for v in scored.values()),
        "image_detected": sum(v["image_detected"] for v in scored.values()),
        "patches_generated": sum(v["patches_generated"] for v in scored.values()),
        "patches_needs_review": sum(v["patches_needs_review"] for v in scored.values()),
        "llm_calls_saved": sum(v["llm_calls_saved"] for v in scored.values()),
        "grep_text_planted": sum(v["grep_baseline"]["text_planted"] for v in scored.values()),
        "grep_text_detected": sum(v["grep_baseline"]["text_detected"] for v in scored.values()),
        "grep_decoys_wrongly_flagged": sum(
            v["grep_baseline"]["decoys_wrongly_flagged"] for v in scored.values()
        ),
        "runtime_s": round(sum(v["runtime_s"] for v in scored.values()), 3),
    }
    agg["text_recall"] = (
        agg["text_detected"] / agg["text_planted"] if agg["text_planted"] else None
    )
    agg["image_recall"] = (
        agg["image_detected"] / agg["image_planted"] if agg["image_planted"] else None
    )
    agg["grep_text_recall"] = (
        agg["grep_text_detected"] / agg["grep_text_planted"] if agg["grep_text_planted"] else None
    )

    def pct(v):
        return "n/a" if v is None else f"{v * 100:.1f}%"

    print("\n" + "=" * 78)
    print(f"model: {model}   mode: {'llm' if args.llm else 'no-llm'}")
    print(f"text recall          : {pct(agg['text_recall'])}  ({agg['text_detected']}/{agg['text_planted']})")
    print(f"image recall         : {pct(agg['image_recall'])}"
          + ("" if agg["image_planted"] else "  (no image ground truth yet)"))
    print(f"decoys wrongly flagged: {agg['decoys_wrongly_flagged']}/{agg['decoys']}")
    print(f"llm calls saved      : {agg['llm_calls_saved']}"
          + (f"  (calls made: {llm_calls_made})" if args.llm else "  (judge skipped)"))
    print(f"patch validity       : {agg['patches_generated']} generated, "
          f"{agg['patches_needs_review']} need review")
    print(f"runtime              : {agg['runtime_s']}s total")
    print(f"naive grep baseline  : recall {pct(agg['grep_text_recall'])}, "
          f"decoys flagged {agg['grep_decoys_wrongly_flagged']}/{agg['decoys']}")
    print("=" * 78)

    results = {
        "model": model,
        "mode": "llm" if args.llm else "no-llm",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runtime_s": agg["runtime_s"],
        "llm": {"enabled": args.llm, "calls_made": llm_calls_made, "calls_saved": agg["llm_calls_saved"]},
        "aggregate": agg,
        "fixtures": per_fixture,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    safe_model = re.sub(r"[^\w.\-]+", "_", model)
    out_path = RESULTS_DIR / f"{safe_model}.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"results written: {out_path}")

    # exit non-zero only on scan errors, not on planted drift findings
    return 1 if any("error" in v for v in per_fixture.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
