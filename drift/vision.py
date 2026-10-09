from __future__ import annotations

import os
import logging
from pathlib import Path
from typing import Optional, Any

from .models import Claim
from .llm import LLMClient, LLMError, chat_json

logger = logging.getLogger("drift.vision")

DEFAULT_VISION_PROMPT = """Analyze this screenshot / image from a web development repository (e.g. terminal output, .env file, Swagger/API doc, browser UI).
Identify any documented facts or configuration claims visible in the image:
- npm_script: commands or scripts executed (e.g. npm run dev:local, pnpm start)
- env_var: environment variables or config keys (e.g. PORT=3000, DATABASE_URL=...)
- route: HTTP API routes or paths (e.g. GET /api/users, http://localhost:3000/api)
- port: server listening ports (e.g. 3000, 8080)
- engine: Node/runtime versions (e.g. v20.11.0)

Output ONLY valid JSON matching this schema:
{
  "image_type": "terminal",
  "claims": [
    {
      "kind": "port",
      "text": "ready on http://localhost:3000",
      "quote": "http://localhost:3000"
    }
  ]
}

Rules:
1. image_type must be one of: "terminal", "env", "api", "ui", "other".
2. For low-quality, blurry, meme, icon, or irrelevant images without clear web config/code claims, return:
   {"image_type": "other", "claims": []}
3. Each claim must have:
   - kind: one of "npm_script", "env_var", "route", "port", "engine"
   - text: the full assertion or sentence found
   - quote: exact verbatim substring read from the image
4. Return JSON only. No prose, no code fences."""

VALID_IMAGE_TYPES = {"terminal", "env", "api", "ui", "other"}

KIND_NORMALIZATION = {
    "npm_script": "npm_script",
    "npm_scripts": "npm_script",
    "script": "npm_script",
    "scripts": "npm_script",
    "env_var": "env_var",
    "env_vars": "env_var",
    "env": "env_var",
    "route": "route",
    "routes": "route",
    "api_route": "route",
    "api_routes": "route",
    "port": "port",
    "ports": "port",
    "engine": "engine",
    "engines": "engine",
    "node_version": "engine",
    "dependency": "dependency",
    "dependencies": "dependency",
    "component_prop": "component_prop",
    "component_props": "component_prop",
}


def _load_vision_prompt() -> str:
    """Load Section C from references/prompts.md if available, else fallback."""
    candidate_paths = [
        Path("references/prompts.md"),
        Path(__file__).resolve().parent.parent / "references" / "prompts.md",
    ]
    for p in candidate_paths:
        if p.is_file():
            try:
                content = p.read_text(encoding="utf-8")
                if "## C." in content:
                    section_c = content.split("## C.")[1].strip()
                    if section_c:
                        return section_c
            except Exception:
                pass
    return DEFAULT_VISION_PROMPT


def extract_claims(
    image_path: str | Path,
    context: str = "",
    doc_file: Optional[str] = None,
    line: int = 0,
    llm: Optional[LLMClient] = None,
) -> list[Claim]:
    """Extract web configuration claims from an image using Gemma 4 vision capabilities.
    
    Returns an empty list when:
    - the image cannot be read or found
    - there is no relevant text
    - image_type is "other" (for low-quality, blurry, or irrelevant images)
    - LLM call fails
    """
    path_obj = Path(image_path)
    if not path_obj.is_file():
        logger.warning("Image file does not exist: %s", image_path)
        return []

    vision_prompt = _load_vision_prompt()
    user_msg_content = f"Image context: {context}\n\n{vision_prompt}" if context else vision_prompt

    messages = [
        {"role": "user", "content": user_msg_content}
    ]

    try:
        if llm is not None:
            data = llm.chat_json(messages, images=[str(path_obj)], required_keys=["image_type"])
        else:
            data = chat_json(messages, images=[str(path_obj)], required_keys=["image_type"])
    except LLMError as err:
        logger.warning("Vision LLM call failed for %s: %s", image_path, err)
        return []
    except Exception as exc:
        logger.warning("Unexpected error extracting claims from %s: %s", image_path, exc)
        return []

    image_type = str(data.get("image_type", "other")).strip().lower()

    # Drop low-quality or non-matching image types
    if image_type not in VALID_IMAGE_TYPES or image_type == "other":
        return []

    raw_claims = data.get("claims", [])
    if not isinstance(raw_claims, list):
        return []

    valid_claims: list[Claim] = []
    for item in raw_claims:
        if not isinstance(item, dict):
            continue

        raw_kind = str(item.get("kind", "")).strip().lower()
        normalized_kind = KIND_NORMALIZATION.get(raw_kind)
        if not normalized_kind:
            continue

        text = str(item.get("text", "")).strip()
        quote = str(item.get("quote", "")).strip()
        if not text or not quote:
            continue

        valid_claims.append(
            Claim(
                kind=normalized_kind,
                text=text,
                doc_file=doc_file or str(path_obj.as_posix()),
                line=line,
                context=context or f"Screenshot: {path_obj.name}",
                source="image",
                image_path=str(path_obj.as_posix()),
                extracted_text=quote,
            )
        )

    return valid_claims
