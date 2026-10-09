import subprocess
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from drift.models import Finding, Claim, Fact
from drift.judge import judge, JUDGE_STATS, reset_stats
from drift.patch import patch, combined_patch, get_deterministic_correction
from drift.llm import LLMError


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a temporary initialized git repo with configured committer."""
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True, check=True)
    return tmp_path


# 1. 12 SUSPECT + 3 OK -> 3 calls, OK untouched, stats correct
def test_judge_batches_and_stats():
    reset_stats()
    suspect_findings = []
    for i in range(12):
        c = Claim(
            kind="npm_script",
            text=f"script_{i}",
            doc_file="README.md",
            line=i + 1,
            context="run script",
            source="text",
        )
        fact = Fact(
            kind="npm_script",
            name=f"script_{i}_real",
            detail="cmd",
            file="package.json",
            line=10,
        )
        suspect_findings.append(
            Finding(claim=c, status="SUSPECT", reason="checking", evidence=[fact])
        )

    ok_findings = []
    for i in range(3):
        c = Claim(
            kind="npm_script",
            text=f"ok_script_{i}",
            doc_file="README.md",
            line=100 + i,
            context="run ok",
            source="text",
        )
        ok_findings.append(Finding(claim=c, status="OK", reason="already ok"))

    all_findings = suspect_findings + ok_findings

    mock_llm = MagicMock()
    # Batch sizes: 5, 5, 2
    mock_llm.chat_json.side_effect = [
        {"verdicts": [{"id": j, "status": "stale", "reason": f"see package.json:10 script_{j-1}_real", "confidence": 0.95} for j in range(1, 6)]},
        {"verdicts": [{"id": j, "status": "stale", "reason": f"see package.json:10 script_{j+4}_real", "confidence": 0.95} for j in range(1, 6)]},
        {"verdicts": [{"id": j, "status": "stale", "reason": f"see package.json:10 script_{j+9}_real", "confidence": 0.95} for j in range(1, 3)]},
    ]

    result = judge(all_findings, llm=mock_llm)

    assert mock_llm.chat_json.call_count == 3
    assert JUDGE_STATS["suspect_total"] == 12
    assert JUDGE_STATS["calls_made"] == 3
    assert JUDGE_STATS["verdicts_accepted"] == 12
    assert JUDGE_STATS["verdicts_dropped"] == 0

    # OK findings untouched
    for i in range(3):
        assert result[12 + i].status == "OK"
        assert result[12 + i].reason == "already ok"

    # SUSPECT findings updated to STALE
    for i in range(12):
        assert result[i].status == "STALE"
        assert result[i].source == "llm"
        assert result[i].confidence == 0.95


# 2. low-confidence and uncited verdicts dropped
def test_low_confidence_and_uncited_dropped():
    reset_stats()
    fact1 = Fact(kind="env_var", name="PORT", detail="3000", file="server.js", line=12)
    c1 = Claim(kind="env_var", text="PORT", doc_file="README.md", line=1, context="ctx", source="text")
    f1 = Finding(claim=c1, status="SUSPECT", reason="check", evidence=[fact1])

    fact2 = Fact(kind="npm_script", name="dev:local", detail="cmd", file="package.json", line=5)
    c2 = Claim(kind="npm_script", text="dev", doc_file="README.md", line=2, context="ctx", source="text")
    f2 = Finding(claim=c2, status="SUSPECT", reason="check", evidence=[fact2])

    fact3 = Fact(kind="route", name="/api/v2/users", detail="router", file="routes.ts", line=20)
    c3 = Claim(kind="route", text="/api/users", doc_file="README.md", line=3, context="ctx", source="text")
    f3 = Finding(claim=c3, status="SUSPECT", reason="check", evidence=[fact3])

    mock_llm = MagicMock()
    mock_llm.chat_json.return_value = {
        "verdicts": [
            # Low confidence (< 0.6)
            {"id": 1, "status": "stale", "reason": "server.js:12 has PORT", "confidence": 0.4},
            # High confidence but uncited reason
            {"id": 2, "status": "stale", "reason": "The script name is different from usual", "confidence": 0.95},
            # Valid: high confidence and cites fact
            {"id": 3, "status": "stale", "reason": "routes.ts:20 has /api/v2/users", "confidence": 0.9},
        ]
    }

    res = judge([f1, f2, f3], llm=mock_llm)

    assert res[0].status == "SUSPECT"
    assert "confidence" in getattr(res[0], "note", "")

    assert res[1].status == "SUSPECT"
    assert "does not cite" in getattr(res[1], "note", "")

    assert res[2].status == "STALE"
    assert res[2].confidence == 0.9

    assert JUDGE_STATS["verdicts_dropped"] == 2
    assert JUDGE_STATS["verdicts_accepted"] == 1


# 3. malformed twice -> stays SUSPECT; LLMError handled
def test_llm_error_handled_stays_suspect():
    reset_stats()
    fact = Fact(kind="npm_script", name="build", detail="next build", file="package.json", line=4)
    c = Claim(kind="npm_script", text="build", doc_file="README.md", line=1, context="ctx", source="text")
    f = Finding(claim=c, status="SUSPECT", reason="check", evidence=[fact])

    mock_llm = MagicMock()
    mock_llm.chat_json.side_effect = LLMError("Malformed JSON repair failed")

    res = judge([f], llm=mock_llm)
    assert res[0].status == "SUSPECT"
    assert getattr(res[0], "note", "") == "judge unavailable"
    assert JUDGE_STATS["llm_unavailable"] == 1


# 4. image quote in prompt
def test_image_quote_in_prompt():
    reset_stats()
    fact = Fact(kind="port", name="3000", detail="listen(3000)", file="server.js", line=10)
    c = Claim(
        kind="port",
        text="port 3000",
        doc_file="README.md",
        line=1,
        context="terminal capture",
        source="image",
        image_path="terminal.png",
        extracted_text="ready on http://localhost:3000",
    )
    f = Finding(claim=c, status="SUSPECT", reason="check", evidence=[fact])

    mock_llm = MagicMock()
    mock_llm.chat_json.return_value = {
        "verdicts": [
            {"id": 1, "status": "ok", "reason": "server.js:10 shows 3000 matches image", "confidence": 0.95}
        ]
    }

    judge([f], llm=mock_llm)
    sent_payload = mock_llm.chat_json.call_args[0][0][1]["content"]
    import json
    data = json.loads(sent_payload)
    assert data["findings"][0]["extracted_quote"] == "ready on http://localhost:3000"


# 5. script rename
def test_patch_script_rename(git_repo: Path):
    doc = git_repo / "README.md"
    doc.write_text("Run npm run dev:locl to start the app.\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=git_repo, check=True)
    subprocess.run(["git", "commit", "-m", "add readme"], cwd=git_repo, check=True)

    fact = Fact(kind="npm_script", name="dev:local", detail="next dev", file="package.json", line=5)
    c = Claim(kind="npm_script", text="npm run dev:locl", doc_file="README.md", line=1, context="ctx", source="text")
    f = Finding(claim=c, status="STALE", reason="old script", evidence=[fact])

    res = patch([f], repo=git_repo)
    assert res[0].patch is not None
    assert "-Run npm run dev:locl to start the app." in res[0].patch
    assert "+Run npm run dev:local to start the app." in res[0].patch
    assert getattr(res[0], "needs_review") is False


# 6. env prefix fix
def test_patch_env_prefix_fix(git_repo: Path):
    doc = git_repo / "env.md"
    doc.write_text("Configure API_URL in your project settings.\n", encoding="utf-8")
    subprocess.run(["git", "add", "env.md"], cwd=git_repo, check=True)
    subprocess.run(["git", "commit", "-m", "add env doc"], cwd=git_repo, check=True)

    fact = Fact(kind="env_var", name="NEXT_PUBLIC_API_URL", detail="client-exposed", file="app/page.tsx", line=2)
    c = Claim(kind="env_var", text="API_URL", doc_file="env.md", line=1, context="ctx", source="text")
    f = Finding(claim=c, status="STALE", reason="prefix missing", evidence=[fact])

    res = patch([f], repo=git_repo)
    assert res[0].patch is not None
    assert "+Configure NEXT_PUBLIC_API_URL in your project settings." in res[0].patch


# 7. /api/users -> /api/v2/users keeps method
def test_patch_route_keeps_method(git_repo: Path):
    doc = git_repo / "api.md"
    doc.write_text("Call GET /api/users to fetch records.\n", encoding="utf-8")
    subprocess.run(["git", "add", "api.md"], cwd=git_repo, check=True)
    subprocess.run(["git", "commit", "-m", "add api doc"], cwd=git_repo, check=True)

    fact = Fact(kind="route", name="/api/v2/users", detail="router", file="app/api/v2/users/route.ts", line=1)
    c = Claim(kind="route", text="GET /api/users", doc_file="api.md", line=1, context="ctx", source="text")
    f = Finding(claim=c, status="STALE", reason="old endpoint", evidence=[fact])

    res = patch([f], repo=git_repo)
    assert res[0].patch is not None
    assert "+Call GET /api/v2/users to fetch records." in res[0].patch


# 8. duplicate span -> null
def test_patch_duplicate_span_null(git_repo: Path):
    doc = git_repo / "dup.md"
    doc.write_text("Run pnpm dev:locl then pnpm dev:locl once more.\n", encoding="utf-8")
    subprocess.run(["git", "add", "dup.md"], cwd=git_repo, check=True)
    subprocess.run(["git", "commit", "-m", "add dup doc"], cwd=git_repo, check=True)

    fact = Fact(kind="npm_script", name="dev:local", detail="cmd", file="package.json", line=5)
    c = Claim(kind="npm_script", text="pnpm dev:locl", doc_file="dup.md", line=1, context="ctx", source="text")
    f = Finding(claim=c, status="STALE", reason="stale script", evidence=[fact])

    res = patch([f], repo=git_repo)
    assert res[0].patch is None
    assert getattr(res[0], "needs_review") is True
    assert "occurs 2 times" in getattr(res[0], "note", "")


# 9. CRLF preserved
def test_patch_crlf_preserved(git_repo: Path):
    doc = git_repo / "crlf.md"
    doc.write_bytes(b"Line 1\r\nRun npm run dev:locl\r\nLine 3\r\n")
    subprocess.run(["git", "add", "crlf.md"], cwd=git_repo, check=True)
    subprocess.run(["git", "commit", "-m", "add crlf doc"], cwd=git_repo, check=True)

    fact = Fact(kind="npm_script", name="dev:local", detail="cmd", file="package.json", line=5)
    c = Claim(kind="npm_script", text="npm run dev:locl", doc_file="crlf.md", line=2, context="ctx", source="text")
    f = Finding(claim=c, status="STALE", reason="stale", evidence=[fact])

    res = patch([f], repo=git_repo)
    assert res[0].patch is not None

    # Apply with real git apply
    subprocess.run(["git", "apply", "-"], input=res[0].patch, text=True, cwd=git_repo, check=True)
    content = doc.read_bytes()
    assert b"\r\n" in content
    assert b"npm run dev:local" in content


# 10. combined patch applies
def test_combined_patch_applies(git_repo: Path):
    doc1 = git_repo / "README.md"
    doc1.write_text("Header\nRun npm run dev:locl here\nFooter\n", encoding="utf-8")
    doc2 = git_repo / "CONFIG.md"
    doc2.write_text("Use API_URL for config\n", encoding="utf-8")

    subprocess.run(["git", "add", "README.md", "CONFIG.md"], cwd=git_repo, check=True)
    subprocess.run(["git", "commit", "-m", "add docs"], cwd=git_repo, check=True)

    f1 = Finding(
        claim=Claim(kind="npm_script", text="npm run dev:locl", doc_file="README.md", line=2, context="ctx", source="text"),
        status="STALE",
        reason="stale",
        evidence=[Fact(kind="npm_script", name="dev:local", detail="cmd", file="package.json", line=1)],
    )
    f2 = Finding(
        claim=Claim(kind="env_var", text="API_URL", doc_file="CONFIG.md", line=1, context="ctx", source="text"),
        status="STALE",
        reason="stale",
        evidence=[Fact(kind="env_var", name="NEXT_PUBLIC_API_URL", detail="env", file="page.tsx", line=1)],
    )

    patch([f1, f2], repo=git_repo)
    all_patch = combined_patch([f1, f2], repo=git_repo)
    assert all_patch != ""

    check_res = subprocess.run(["git", "apply", "--check", "-"], input=all_patch, text=True, cwd=git_repo, capture_output=True)
    assert check_res.returncode == 0

    apply_res = subprocess.run(["git", "apply", "-"], input=all_patch, text=True, cwd=git_repo, capture_output=True)
    assert apply_res.returncode == 0
    assert "dev:local" in doc1.read_text(encoding="utf-8")
    assert "NEXT_PUBLIC_API_URL" in doc2.read_text(encoding="utf-8")


# 11. image -> note only
def test_patch_image_note_only(git_repo: Path):
    c = Claim(
        kind="port",
        text="3000",
        doc_file="docs.md",
        line=1,
        context="ctx",
        source="image",
        image_path="screenshots/terminal.png",
        extracted_text="ready on http://localhost:3000",
    )
    fact = Fact(kind="port", name="3001", detail="listen(3001)", file="server.js", line=10)
    f = Finding(claim=c, status="STALE", reason="port changed", evidence=[fact])

    res = patch([f], repo=git_repo)
    assert res[0].patch is None
    expected_note = "Replace image screenshots/terminal.png: shows 'ready on http://localhost:3000' but code has '3001'"
    assert getattr(res[0], "note", "") == expected_note
