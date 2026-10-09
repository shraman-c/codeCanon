from pathlib import Path
from unittest.mock import MagicMock
import pytest

from drift.vision import extract_claims
from drift.llm import LLMError


def test_extract_claims_valid_terminal(tmp_path: Path):
    img = tmp_path / "terminal.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\nfakeimage")

    mock_llm = MagicMock()
    mock_llm.chat_json.return_value = {
        "image_type": "terminal",
        "claims": [
            {
                "kind": "ports",
                "text": "ready on http://localhost:3000",
                "quote": "http://localhost:3000",
            },
            {
                "kind": "npm_scripts",
                "text": "$ npm run dev:local",
                "quote": "npm run dev:local",
            },
        ],
    }

    claims = extract_claims(img, context="Terminal output", llm=mock_llm)
    assert len(claims) == 2
    assert claims[0].kind == "port"
    assert claims[0].text == "ready on http://localhost:3000"
    assert claims[0].extracted_text == "http://localhost:3000"
    assert claims[0].source == "image"
    assert claims[0].image_path == str(img.as_posix())

    assert claims[1].kind == "npm_script"
    assert claims[1].text == "$ npm run dev:local"
    assert claims[1].extracted_text == "npm run dev:local"


def test_extract_claims_other_returns_empty(tmp_path: Path):
    img = tmp_path / "blurry.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\nblurry")

    mock_llm = MagicMock()
    mock_llm.chat_json.return_value = {
        "image_type": "other",
        "claims": [],
    }

    claims = extract_claims(img, context="Blurry photo", llm=mock_llm)
    assert claims == []


def test_extract_claims_low_quality_filtered(tmp_path: Path):
    img = tmp_path / "icon.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\nicon")

    mock_llm = MagicMock()
    mock_llm.chat_json.return_value = {
        "image_type": "ui",
        "claims": [
            {
                "kind": "unknown_nonsense",
                "text": "nothing valid",
                "quote": "quote",
            },
            {
                "kind": "route",
                "text": "",  # Empty text
                "quote": "valid",
            },
        ],
    }

    claims = extract_claims(img, llm=mock_llm)
    assert claims == []


def test_extract_claims_missing_image_file():
    claims = extract_claims("nonexistent_path/terminal.png")
    assert claims == []


def test_extract_claims_llm_error_handled(tmp_path: Path):
    img = tmp_path / "terminal.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\nfakeimage")

    mock_llm = MagicMock()
    mock_llm.chat_json.side_effect = LLMError("API timeout")

    claims = extract_claims(img, llm=mock_llm)
    assert claims == []
