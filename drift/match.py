from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from typing import Literal

from .models import Claim, Fact, Finding

Status = Literal["OK", "STALE", "SUSPECT"]

BUILTIN_SCRIPTS = {"start", "test", "install", "ci"}

ENV_ALLOWLIST = {"NODE_ENV", "PORT", "HOME", "PATH", "CI"}

GENERIC_ALLOWLIST = {
    "--help",
    "--version",
    "localhost",
    "YOUR_API_KEY",
    "xxx",
}

PLACEHOLDER_PREFIXES = ("YOUR_", "<your-")

ROUTE_PARAM_PATTERN = re.compile(r"[:{[]\w+[}\]]|:\w+")


def _fuzzy_ratio(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _normalize_route(path: str) -> str:
    path = path.strip()
    path = ROUTE_PARAM_PATTERN.sub(":param", path)
    # Also normalize numeric path segments (e.g., /api/users/123 -> /api/users/:param)
    path = re.sub(r"/\d+(?=/|$)", "/:param", path)
    if path.endswith("/") and len(path) > 1:
        path = path[:-1]
    return path.lower()


def _extract_method_and_path(text: str) -> tuple[str | None, str]:
    parts = text.strip().split(None, 1)
    if len(parts) == 2 and parts[0].upper() in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}:
        return parts[0].upper(), parts[1]
    return None, text.strip()


def _is_allowlisted(text: str) -> bool:
    text_lower = text.lower()
    if text_lower in GENERIC_ALLOWLIST:
        return True
    # Check for allowlisted tokens as whole words (not part of larger tokens like localhost:3000)
    for token in GENERIC_ALLOWLIST:
        if token == "localhost":
            # Special case: allow "localhost" alone but not "localhost:PORT"
            if re.search(r"(^|[^a-z0-9_])localhost($|[^a-z0-9_:])", text_lower):
                return True
        else:
            if re.search(rf"(^|[^a-z0-9_]){re.escape(token)}([^a-z0-9_]|$)", text_lower):
                return True
    for prefix in PLACEHOLDER_PREFIXES:
        if text_lower.startswith(prefix.lower()):
            return True
    if re.fullmatch(r"[xX*-]+", text):
        return True
    return False


def _is_env_allowlisted(name: str) -> bool:
    return name in ENV_ALLOWLIST


@dataclass
class MatchContext:
    facts_by_kind: dict[str, list[Fact]]

    def get_facts(self, kind: str) -> list[Fact]:
        return self.facts_by_kind.get(kind, [])


def match_claims(claims: list[Claim], facts: list[Fact]) -> list[Finding]:
    facts_by_kind: dict[str, list[Fact]] = {}
    for f in facts:
        facts_by_kind.setdefault(f.kind, []).append(f)

    ctx = MatchContext(facts_by_kind)
    findings: list[Finding] = []

    for claim in claims:
        if _is_allowlisted(claim.text):
            findings.append(
                Finding(
                    claim=claim,
                    status="OK",
                    reason="allowlisted token",
                    evidence=[],
                    confidence=1.0,
                    source="deterministic",
                )
            )
            continue

        if claim.kind == "npm_script":
            findings.append(_match_npm_script(claim, ctx))
        elif claim.kind == "env_var":
            findings.append(_match_env_var(claim, ctx))
        elif claim.kind == "port":
            findings.append(_match_port(claim, ctx))
        elif claim.kind == "engine":
            findings.append(_match_engine(claim, ctx))
        elif claim.kind == "route":
            findings.append(_match_route(claim, ctx))
        elif claim.kind == "dependency":
            findings.append(_match_dependency(claim, ctx))
        elif claim.kind == "code_sample":
            findings.append(_match_code_sample(claim, ctx))
        else:
            findings.append(
                Finding(
                    claim=claim,
                    status="SUSPECT",
                    reason=f"no matcher for kind {claim.kind}",
                    evidence=[],
                    confidence=0.0,
                    source="deterministic",
                )
            )

    return findings


def _match_npm_script(claim: Claim, ctx: MatchContext) -> Finding:
    script_name = claim.text.split()[-1]
    facts = ctx.get_facts("npm_script")

    for fact in facts:
        if fact.name == script_name:
            return Finding(
                claim=claim,
                status="OK",
                reason=f"script '{script_name}' exists in package.json",
                evidence=[fact],
                confidence=1.0,
                source="deterministic",
            )

    if script_name in BUILTIN_SCRIPTS:
        return Finding(
            claim=claim,
            status="OK",
            reason=f"'{script_name}' is a built-in npm script",
            evidence=[],
            confidence=0.9,
            source="deterministic",
        )

    best_ratio = 0.0
    best_fact = None
    for fact in facts:
        ratio = _fuzzy_ratio(script_name, fact.name)
        # Also check if one is a prefix of the other (e.g., dev:local vs dev)
        if script_name.startswith(fact.name + ":") or fact.name.startswith(script_name + ":"):
            ratio = max(ratio, 0.85)
        if ratio > best_ratio:
            best_ratio = ratio
            best_fact = fact

    if best_ratio >= 0.8 and best_fact:
        return Finding(
            claim=claim,
            status="SUSPECT",
            reason=f"script '{script_name}' similar to existing '{best_fact.name}' (similarity={best_ratio:.2f})",
            evidence=[best_fact],
            confidence=best_ratio,
            source="deterministic",
        )

    return Finding(
        claim=claim,
        status="STALE",
        reason=f"script '{script_name}' not found in package.json",
        evidence=[],
        confidence=1.0,
        source="deterministic",
    )


def _match_env_var(claim: Claim, ctx: MatchContext) -> Finding:
    name = claim.text.split("=")[0].strip()
    facts = ctx.get_facts("env_var")

    for fact in facts:
        if fact.name == name:
            return Finding(
                claim=claim,
                status="OK",
                reason=f"env var '{name}' found in code or .env.example",
                evidence=[fact],
                confidence=1.0,
                source="deterministic",
            )

    if _is_env_allowlisted(name):
        return Finding(
            claim=claim,
            status="OK",
            reason=f"env var '{name}' is allowlisted",
            evidence=[],
            confidence=0.9,
            source="deterministic",
        )

    best_ratio = 0.0
    best_fact = None
    prefix_mismatch = False
    for fact in facts:
        ratio = _fuzzy_ratio(name, fact.name)
        if ratio > best_ratio:
            best_ratio = ratio
            best_fact = fact
        if _has_prefix_mismatch(name, fact.name):
            prefix_mismatch = True

    if prefix_mismatch:
        return Finding(
            claim=claim,
            status="SUSPECT",
            reason=f"env var '{name}' has different prefix than existing vars (e.g., NEXT_PUBLIC_ vs VITE_)",
            evidence=[best_fact] if best_fact else [],
            confidence=0.7,
            source="deterministic",
        )

    if best_ratio >= 0.8 and best_fact:
        return Finding(
            claim=claim,
            status="SUSPECT",
            reason=f"env var '{name}' similar to existing '{best_fact.name}' (similarity={best_ratio:.2f})",
            evidence=[best_fact],
            confidence=best_ratio,
            source="deterministic",
        )

    return Finding(
        claim=claim,
        status="STALE",
        reason=f"env var '{name}' not found in code or .env.example",
        evidence=[],
        confidence=1.0,
        source="deterministic",
    )


def _has_prefix_mismatch(a: str, b: str) -> bool:
    a_prefix = _get_env_prefix(a)
    b_prefix = _get_env_prefix(b)
    return bool(a_prefix != b_prefix and a_prefix and b_prefix)


def _get_env_prefix(name: str) -> str:
    for prefix in ("NEXT_PUBLIC_", "VITE_", "REACT_APP_"):
        if name.startswith(prefix):
            return prefix
    return ""


def _match_port(claim: Claim, ctx: MatchContext) -> Finding:
    if _is_allowlisted(claim.text):
        return Finding(
            claim=claim,
            status="OK",
            reason="allowlisted token",
            evidence=[],
            confidence=1.0,
            source="deterministic",
        )

    port_match = re.search(r"(\d{2,5})", claim.text)
    if not port_match:
        return Finding(
            claim=claim,
            status="SUSPECT",
            reason="could not extract port number from claim",
            evidence=[],
            confidence=0.0,
            source="deterministic",
        )

    claimed_port = int(port_match.group(1))
    facts = ctx.get_facts("port")

    matching = [f for f in facts if str(claimed_port) in f.detail]
    if len(matching) == 1:
        return Finding(
            claim=claim,
            status="OK",
            reason=f"port {claimed_port} matches detected port",
            evidence=matching,
            confidence=1.0,
            source="deterministic",
        )

    if len(matching) > 1:
        return Finding(
            claim=claim,
            status="SUSPECT",
            reason=f"port {claimed_port} matches multiple detected ports",
            evidence=matching,
            confidence=0.6,
            source="deterministic",
        )

    return Finding(
        claim=claim,
        status="STALE",
        reason=f"port {claimed_port} not found in any detected port",
        evidence=facts,
        confidence=1.0,
        source="deterministic",
    )


def _match_engine(claim: Claim, ctx: MatchContext) -> Finding:
    version_match = re.search(r"(\d{1,2}(?:\.\d+){1,2})", claim.text)
    if not version_match:
        return Finding(
            claim=claim,
            status="SUSPECT",
            reason="could not extract version from claim",
            evidence=[],
            confidence=0.0,
            source="deterministic",
        )

    claimed_version = version_match.group(1)
    claimed_major = int(claimed_version.split(".")[0])

    facts = ctx.get_facts("engine")
    if not facts:
        return Finding(
            claim=claim,
            status="OK",
            reason="no engine info in repo; skipping check",
            evidence=[],
            confidence=0.5,
            source="deterministic",
        )

    for fact in facts:
        # Extract version from engine spec like ">=20", "20.10.0", ">=20.0.0"
        fact_version_match = re.search(r"(\d{1,2}(?:\.\d+){0,2})", fact.detail)
        if fact_version_match:
            fact_version_str = fact_version_match.group(1)
            fact_major = int(fact_version_str.split(".")[0])
            if claimed_major >= fact_major:
                return Finding(
                    claim=claim,
                    status="OK",
                    reason=f"claimed node {claimed_version} satisfies engines ({fact.detail})",
                    evidence=[fact],
                    confidence=1.0,
                    source="deterministic",
                )
            else:
                return Finding(
                    claim=claim,
                    status="STALE",
                    reason=f"claimed node {claimed_version} below required {fact.detail}",
                    evidence=[fact],
                    confidence=1.0,
                    source="deterministic",
                )

    return Finding(
        claim=claim,
        status="SUSPECT",
        reason="engine fact present but version format unrecognized",
        evidence=facts,
        confidence=0.3,
        source="deterministic",
    )


def _match_route(claim: Claim, ctx: MatchContext) -> Finding:
    method, path = _extract_method_and_path(claim.text)
    norm_claimed = _normalize_route(path)

    facts = ctx.get_facts("route")

    for fact in facts:
        fact_method, fact_path = _extract_method_and_path(fact.detail)
        norm_fact = _normalize_route(fact_path)

        if norm_claimed == norm_fact:
            if method and fact_method and method != fact_method:
                return Finding(
                    claim=claim,
                    status="SUSPECT",
                    reason=f"route path matches but method differs: claimed {method}, code has {fact_method}",
                    evidence=[fact],
                    confidence=0.8,
                    source="deterministic",
                )
            return Finding(
                claim=claim,
                status="OK",
                reason=f"route {method or '?'} {path} matches code route",
                evidence=[fact],
                confidence=1.0,
                source="deterministic",
            )

    for fact in facts:
        _, fact_path = _extract_method_and_path(fact.detail)
        norm_fact = _normalize_route(fact_path)
        if _is_similar_prefix(norm_claimed, norm_fact):
            return Finding(
                claim=claim,
                status="SUSPECT",
                reason=f"route '{path}' similar to existing '{fact_path}' (possible version prefix change)",
                evidence=[fact],
                confidence=0.7,
                source="deterministic",
            )

    return Finding(
        claim=claim,
        status="STALE",
        reason=f"route '{claim.text}' not found in code routes",
        evidence=facts,
        confidence=1.0,
        source="deterministic",
    )


def _is_similar_prefix(a: str, b: str) -> bool:
    if a == b:
        return False
    parts_a = a.strip("/").split("/")
    parts_b = b.strip("/").split("/")
    if len(parts_a) < 2 or len(parts_b) < 2:
        return False

    # Check if first segment matches (e.g., both start with 'api')
    if parts_a[0] != parts_b[0]:
        return False

    # Check if one path is the other with a version segment inserted/removed
    # e.g., /api/users vs /api/v2/users
    # Normalize by removing version-like segments (v\d+, \d+\.\d+)
    def _strip_version(parts: list[str]) -> list[str]:
        return [p for p in parts if not re.match(r"^v?\d+(\.\d+)?$", p)]

    stripped_a = _strip_version(parts_a)
    stripped_b = _strip_version(parts_b)

    return stripped_a == stripped_b and parts_a != parts_b


def _match_dependency(claim: Claim, ctx: MatchContext) -> Finding:
    facts = ctx.get_facts("dependency")
    claimed_name = claim.text.split()[0].strip("`")

    for fact in facts:
        if fact.name.lower() == claimed_name.lower():
            return Finding(
                claim=claim,
                status="OK",
                reason=f"dependency '{claimed_name}' found in package.json",
                evidence=[fact],
                confidence=1.0,
                source="deterministic",
            )

    best_ratio = 0.0
    best_fact = None
    for fact in facts:
        ratio = _fuzzy_ratio(claimed_name, fact.name)
        if ratio > best_ratio:
            best_ratio = ratio
            best_fact = fact

    if best_ratio >= 0.8 and best_fact:
        return Finding(
            claim=claim,
            status="SUSPECT",
            reason=f"dependency '{claimed_name}' similar to '{best_fact.name}' (similarity={best_ratio:.2f})",
            evidence=[best_fact],
            confidence=best_ratio,
            source="deterministic",
        )

    return Finding(
        claim=claim,
        status="STALE",
        reason=f"dependency '{claimed_name}' not found in package.json",
        evidence=[],
        confidence=1.0,
        source="deterministic",
    )


def _match_code_sample(claim: Claim, ctx: MatchContext) -> Finding:
    return Finding(
        claim=claim,
        status="SUSPECT",
        reason="code sample checking not implemented in deterministic matcher",
        evidence=[],
        confidence=0.0,
        source="deterministic",
    )


def apply_image_discount(findings: list[Finding]) -> list[Finding]:
    for finding in findings:
        if finding.claim.source == "image":
            if finding.status == "STALE":
                quote = finding.claim.extracted_text or ""
                if len(quote) < 20 or quote.count(" ") < 3:
                    finding.status = "SUSPECT"
                    finding.reason = f"[image] {finding.reason} (downgraded from STALE: short/ambiguous quote)"
                    finding.confidence = min(finding.confidence, 0.6)
    return findings