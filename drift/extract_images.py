from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Iterator

from .models import Claim

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
DEFAULT_MAX_IMAGES = 10
DEFAULT_MAX_SIZE_BYTES = 1_500_000

MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
HTML_IMG_RE = re.compile(r'<img\s+[^>]*src=["\']([^"\']+)["\'][^>]*>', re.IGNORECASE)


def _image_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _resolve_image_path(doc_path: Path, img_src: str, repo_root: Path) -> Path | None:
    """Resolve image src to absolute path within repo."""
    if img_src.startswith(("http://", "https://", "data:")):
        return None
    candidate = (doc_path.parent / img_src).resolve()
    try:
        candidate.relative_to(repo_root)
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def _iter_image_refs(doc_path: Path) -> Iterator[str]:
    text = doc_path.read_text(encoding="utf-8", errors="ignore")
    for m in MD_IMAGE_RE.finditer(text):
        yield m.group(1)
    for m in HTML_IMG_RE.finditer(text):
        yield m.group(1)


def extract_image_claims(
    repo_root: Path,
    doc_paths: list[Path],
    max_images: int = DEFAULT_MAX_IMAGES,
    max_size_bytes: int = DEFAULT_MAX_SIZE_BYTES,
) -> Iterator[Claim]:
    """Extract claims from images in documentation files.

    Yields Claim objects with source="image", image_path, and extracted_text.
    The actual vision extraction is delegated to drift.vision (Member C).
    """
    from . import vision

    seen_hashes: set[str] = set()
    count = 0

    for doc_path in doc_paths:
        if count >= max_images:
            break

        for img_src in _iter_image_refs(doc_path):
            if count >= max_images:
                break

            img_path = _resolve_image_path(doc_path, img_src, repo_root)
            if img_path is None:
                continue
            if img_path.suffix.lower() not in IMAGE_EXTS:
                continue
            if img_path.stat().st_size > max_size_bytes:
                continue

            img_hash = _image_hash(img_path)
            if img_hash in seen_hashes:
                continue
            seen_hashes.add(img_hash)

            try:
                raw_claims = vision.extract_claims(img_path, doc_path.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                continue

            for rc in raw_claims:
                kind = rc.get("kind")
                quote = rc.get("quote", "")
                if not kind or not quote:
                    continue
                yield Claim(
                    kind=kind,
                    text=quote,
                    doc_file=str(doc_path),
                    line=1,
                    context=f"image: {img_path.name}",
                    source="image",
                    image_path=str(img_path.relative_to(repo_root)),
                    extracted_text=quote,
                )
            count += 1


def collect_image_claims(
    repo_root: Path,
    doc_paths: list[Path],
    max_images: int = DEFAULT_MAX_IMAGES,
    max_size_bytes: int = DEFAULT_MAX_SIZE_BYTES,
) -> list[Claim]:
    return list(extract_image_claims(repo_root, doc_paths, max_images, max_size_bytes))