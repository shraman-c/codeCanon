from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Fact:
    """Something that exists in the web repo."""

    kind: str  # npm_script | env_var | route | port | engine | dependency | component_prop
    name: str
    detail: str
    file: str
    line: int


@dataclass(frozen=True)
class Claim:
    """Something the docs assert."""

    kind: str  # same kinds + code_sample
    text: str
    doc_file: str
    line: int
    context: str
    source: str  # text | image
    image_path: str | None = None
    extracted_text: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "text": self.text,
            "doc_file": self.doc_file,
            "line": self.line,
            "context": self.context,
            "source": self.source,
            "image_path": self.image_path,
            "extracted_text": self.extracted_text,
        }


@dataclass
class Finding:
    """One drift verdict on a single claim."""

    claim: Claim
    status: str  # OK | STALE | SUSPECT
    reason: str
    evidence: list[Fact] = field(default_factory=list)
    confidence: float = 0.0
    patch: str | None = None  # null for image findings
    source: str = "deterministic"  # deterministic | llm

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim": self.claim.to_dict(),
            "status": self.status,
            "reason": self.reason,
            "evidence": [e.__dict__ for e in self.evidence],
            "confidence": self.confidence,
            "patch": self.patch,
            "source": self.source,
        }
