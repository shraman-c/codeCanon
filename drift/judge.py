from __future__ import annotations

import os
import json
import logging
from pathlib import Path
from typing import Any, Optional

from .models import Finding, Fact, Claim
from .llm import LLMClient, LLMError, chat_json

logger = logging.getLogger("drift.judge")

DEFAULT_SYSTEM_PROMPT = """You are an expert documentation drift judge analyzing discrepancies between code facts and documentation claims in JS/TS web repositories.
You receive a batch of up to 5 suspect findings. Each finding contains:
- id: Unique finding identifier
- claim_text: The statement found in docs or markdown
- context: Surrounding documentation context
- extracted_quote: For image/screenshot claims, the text detected in the image
- candidate_facts: Codebase facts with kind, name, detail, and file:line

Evaluate each finding strictly based on the provided candidate facts.

Output ONLY valid JSON matching this schema:
{
  "verdicts": [
    {
      "id": 1,
      "status": "stale",
      "reason": "Docs state npm start, but package.json:12 defines scripts.start as node server.js.",
      "corrected_text": "node server.js",
      "confidence": 0.95
    }
  ]
}

Rules:
1. status must be "stale" or "ok".
2. In reason, ALWAYS cite which candidate fact you relied upon by its exact file:line or name.
3. If candidate facts do not provide conclusive proof of drift, return status: "ok" with confidence < 0.5 rather than guessing.
4. Never hallucinate or invent facts not present in candidate_facts.
5. Return JSON only. No prose, explanations, or code fences outside the JSON.

Web Hints:
1. Route Equivalence: [id] = :id = {id}. Dynamic routes like /users/[id] and /users/:id represent the same route.
2. Env Var Visibility: NEXT_PUBLIC_* (Next.js) and VITE_* (Vite) are bundled to client-side. API_URL vs NEXT_PUBLIC_API_URL is a functional distinction.
3. Package Manager Script Equivalence: npm run dev, pnpm dev, yarn dev, bun dev are equivalent.
4. Express Route Mount Prefixes: app.use('/prefix', router) prepends /prefix to router definitions."""

JUDGE_STATS: dict[str, int] = {
    "suspect_total": 0,
    "calls_made": 0,
    "verdicts_accepted": 0,
    "verdicts_dropped": 0,
    "llm_unavailable": 0,
}


def reset_stats() -> None:
    """Reset all judge statistics counters to zero."""
    for key in JUDGE_STATS:
        JUDGE_STATS[key] = 0


def _load_prompt_reference() -> str:
    """Load Sections A and B from references/prompts.md if available, else fallback."""
    candidate_paths = [
        Path("references/prompts.md"),
        Path(__file__).resolve().parent.parent / "references" / "prompts.md",
    ]
    for p in candidate_paths:
        if p.is_file():
            try:
                content = p.read_text(encoding="utf-8")
                # Split before Section C if present
                if "## C." in content:
                    content = content.split("## C.")[0].strip()
                if content:
                    return content
            except Exception:
                pass
    return DEFAULT_SYSTEM_PROMPT


def _cites_candidate_fact(reason: str, candidate_facts: list[Fact]) -> bool:
    """Check if the verdict reason cites at least one candidate fact by file:line, file, or name."""
    if not candidate_facts:
        return False
    reason_norm = reason.lower()
    for f in candidate_facts:
        # Check file:line (e.g. package.json:12)
        fl = f"{f.file}:{f.line}".lower()
        if fl in reason_norm:
            return True
        # Check file name (e.g. package.json)
        if f.file and f.file.lower() in reason_norm:
            return True
        # Check fact name (e.g. dev:local, NEXT_PUBLIC_API_URL, /api/v2/users)
        if f.name and f.name.lower() in reason_norm:
            return True
    return False


def judge(findings: list[Finding], llm: Optional[LLMClient] = None) -> list[Finding]:
    """Evaluate SUSPECT findings in batches of up to 5 using Gemma 4 LLM judge."""
    suspects: list[Finding] = [f for f in findings if f.status.upper() == "SUSPECT"]
    JUDGE_STATS["suspect_total"] += len(suspects)

    if not suspects:
        return findings

    system_prompt = _load_prompt_reference()
    threshold = float(os.environ.get("DRIFT_JUDGE_THRESHOLD", "0.6"))
    batch_size = 5

    for i in range(0, len(suspects), batch_size):
        batch = suspects[i : i + batch_size]
        batch_payload: list[dict[str, Any]] = []

        for local_id, f in enumerate(batch, 1):
            claim = f.claim
            extracted_quote = (
                getattr(claim, "extracted_quote", None)
                or getattr(claim, "extracted_text", None)
                or (claim.text if claim.source == "image" else "")
            )
            candidate_facts = [
                {
                    "kind": fact.kind,
                    "name": fact.name,
                    "detail": fact.detail,
                    "file_line": f"{fact.file}:{fact.line}",
                }
                for fact in f.evidence
            ]
            batch_payload.append(
                {
                    "id": local_id,
                    "claim_text": claim.text,
                    "context": claim.context,
                    "extracted_quote": extracted_quote,
                    "candidate_facts": candidate_facts,
                }
            )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps({"findings": batch_payload}, indent=2)},
        ]

        JUDGE_STATS["calls_made"] += 1

        try:
            if llm is not None:
                response_data = llm.chat_json(messages, required_keys=["verdicts"])
            else:
                response_data = chat_json(messages, required_keys=["verdicts"])
        except LLMError as err:
            logger.warning("LLM call failed for judge batch: %s", err)
            JUDGE_STATS["llm_unavailable"] += 1
            for f in batch:
                setattr(f, "note", "judge unavailable")
            continue
        except Exception as exc:
            logger.warning("Unexpected error during judge call: %s", exc)
            JUDGE_STATS["llm_unavailable"] += 1
            for f in batch:
                setattr(f, "note", "judge unavailable")
            continue

        verdicts_list = response_data.get("verdicts", [])
        verdict_by_id: dict[int, dict[str, Any]] = {}
        for v in verdicts_list:
            if isinstance(v, dict) and "id" in v:
                try:
                    verdict_by_id[int(v["id"])] = v
                except (ValueError, TypeError):
                    pass

        for local_id, finding in enumerate(batch, 1):
            verdict = verdict_by_id.get(local_id)
            if not verdict:
                JUDGE_STATS["verdicts_dropped"] += 1
                setattr(finding, "note", "Verdict dropped: no verdict returned for finding id")
                continue

            status = str(verdict.get("status", "")).strip().lower()
            reason = str(verdict.get("reason", "")).strip()
            confidence_raw = verdict.get("confidence")

            try:
                confidence = float(confidence_raw)
            except (ValueError, TypeError):
                confidence = -1.0

            # Validate verdict fields
            if status not in ("stale", "ok") or not reason or confidence < 0.0 or confidence > 1.0:
                JUDGE_STATS["verdicts_dropped"] += 1
                setattr(finding, "note", "Verdict dropped: invalid verdict structure or status")
                continue

            # Drop confidence below threshold
            if confidence < threshold:
                JUDGE_STATS["verdicts_dropped"] += 1
                setattr(
                    finding,
                    "note",
                    f"Verdict dropped: confidence {confidence:.2f} < threshold {threshold:.2f}",
                )
                continue

            # Drop verdicts that do not cite any candidate fact
            if not _cites_candidate_fact(reason, finding.evidence):
                JUDGE_STATS["verdicts_dropped"] += 1
                setattr(
                    finding,
                    "note",
                    "Verdict dropped: reason does not cite any candidate fact",
                )
                continue

            # Accept verdict
            JUDGE_STATS["verdicts_accepted"] += 1
            finding.confidence = confidence
            finding.reason = reason
            finding.source = "llm"

            if status == "stale":
                finding.status = "STALE"
                corrected_text = verdict.get("corrected_text")
                if corrected_text is not None:
                    setattr(finding, "corrected_text", str(corrected_text).strip())
            else:
                finding.status = "OK"

    return findings

