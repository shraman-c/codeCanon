import os
import json
import logging
from unittest.mock import patch, MagicMock
import pytest
import requests

from drift.llm import LLMClient, LLMError


def _mock_response(status_code=200, json_data=None, text="", headers=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = headers or {}
    if json_data is not None:
        resp.json.return_value = json_data
        resp.text = json.dumps(json_data)
    else:
        resp.text = text
        resp.json.side_effect = ValueError("No JSON")
    return resp


# 1. good JSON returns parsed dict
@patch("requests.post")
def test_good_json_returns_parsed_dict(mock_post, tmp_path):
    mock_post.return_value = _mock_response(
        200,
        json_data={
            "choices": [
                {"message": {"content": '{"status": "ok", "id": 1}'}}
            ]
        }
    )
    client = LLMClient(api_key="dummy", cache_dir=str(tmp_path))
    res = client.chat_json([{"role": "user", "content": "analyze"}], required_keys=["status"])
    assert res == {"status": "ok", "id": 1}
    assert mock_post.call_count == 1


# 2. malformed JSON triggers exactly one repair retry, then succeeds
@patch("requests.post")
def test_malformed_json_repair_retry_success(mock_post, tmp_path):
    bad_resp = _mock_response(
        200,
        json_data={
            "choices": [
                {"message": {"content": "Here is the response: {bad_json..."}}
            ]
        }
    )
    good_resp = _mock_response(
        200,
        json_data={
            "choices": [
                {"message": {"content": '```json\n{"status": "fixed", "id": 2}\n```'}}
            ]
        }
    )
    mock_post.side_effect = [bad_resp, good_resp]

    client = LLMClient(api_key="dummy", cache_dir=str(tmp_path))
    res = client.chat_json([{"role": "user", "content": "analyze"}], required_keys=["status"])
    assert res == {"status": "fixed", "id": 2}
    assert mock_post.call_count == 2
    # Ensure second call contains repair instruction
    second_call_payload = mock_post.call_args_list[1].kwargs["json"]
    messages = second_call_payload["messages"]
    assert any("Return ONLY valid JSON" in m.get("content", "") for m in messages)


# 3. malformed JSON twice raises LLMError (no crash)
@patch("requests.post")
def test_malformed_json_twice_raises_llm_error(mock_post, tmp_path):
    bad_resp = _mock_response(
        200,
        json_data={
            "choices": [
                {"message": {"content": "Still not valid JSON: abc"}}
            ]
        }
    )
    mock_post.side_effect = [bad_resp, bad_resp]

    client = LLMClient(api_key="dummy", cache_dir=str(tmp_path))
    with pytest.raises(LLMError) as exc_info:
        client.chat_json([{"role": "user", "content": "analyze"}], required_keys=["status"])

    assert exc_info.value.raw_text == "Still not valid JSON: abc"
    assert mock_post.call_count == 2


# 4. 429 then 200 retries and succeeds; 500 x4 raises
@patch("time.sleep", return_value=None)
@patch("requests.post")
def test_retry_on_429_then_success(mock_post, mock_sleep, tmp_path):
    resp_429 = _mock_response(429, text="Rate limit exceeded", headers={"Retry-After": "0"})
    resp_200 = _mock_response(
        200,
        json_data={
            "choices": [
                {"message": {"content": "hello after retry"}}
            ]
        }
    )
    mock_post.side_effect = [resp_429, resp_200]

    client = LLMClient(api_key="dummy", cache_dir=str(tmp_path))
    ans = client.chat([{"role": "user", "content": "hello"}])
    assert ans == "hello after retry"
    assert mock_post.call_count == 2


@patch("time.sleep", return_value=None)
@patch("requests.post")
def test_retry_on_500_max_attempts_raises(mock_post, mock_sleep, tmp_path):
    resp_500 = _mock_response(500, text="Internal Server Error")
    mock_post.return_value = resp_500

    client = LLMClient(api_key="dummy", cache_dir=str(tmp_path))
    with pytest.raises(LLMError) as exc_info:
        client.chat([{"role": "user", "content": "hello"}])

    assert "after 4 attempts" in str(exc_info.value)
    assert mock_post.call_count == 4


# 5. image message is built as a base64 data URL part on the last user message
@patch("requests.post")
def test_image_message_built_as_base64_data_url(mock_post, tmp_path):
    img_file = tmp_path / "screenshot.png"
    img_file.write_bytes(b"\x89PNG\r\n\x1a\nfakeimagebytes")

    mock_post.return_value = _mock_response(
        200,
        json_data={"choices": [{"message": {"content": "saw image"}}]}
    )

    client = LLMClient(api_key="dummy", cache_dir=str(tmp_path))
    client.chat(
        [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "inspect this image"}
        ],
        images=[str(img_file)]
    )

    assert mock_post.call_count == 1
    sent_payload = mock_post.call_args.kwargs["json"]
    user_msg = sent_payload["messages"][1]
    assert user_msg["role"] == "user"
    assert isinstance(user_msg["content"], list)
    assert user_msg["content"][0] == {"type": "text", "text": "inspect this image"}
    assert user_msg["content"][1]["type"] == "image_url"
    assert user_msg["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")


# 6. system role folding on/off
@patch("requests.post")
def test_system_role_folding(mock_post, tmp_path):
    mock_post.return_value = _mock_response(
        200,
        json_data={"choices": [{"message": {"content": "ok"}}]}
    )

    # Folding off
    client_unfolded = LLMClient(api_key="dummy", fold_system_prompt=False, cache_dir=str(tmp_path))
    client_unfolded.chat([
        {"role": "system", "content": "System directive"},
        {"role": "user", "content": "User input"}
    ])
    payload1 = mock_post.call_args.kwargs["json"]
    roles1 = [m["role"] for m in payload1["messages"]]
    assert roles1 == ["system", "user"]

    # Folding on
    client_folded = LLMClient(api_key="dummy", fold_system_prompt=True, cache_dir=str(tmp_path))
    client_folded.chat([
        {"role": "system", "content": "System directive"},
        {"role": "user", "content": "User input"}
    ])
    payload2 = mock_post.call_args.kwargs["json"]
    roles2 = [m["role"] for m in payload2["messages"]]
    assert "system" not in roles2
    assert roles2 == ["user"]
    assert "System directive\n\nUser input" in payload2["messages"][0]["content"]


# 7. cache hit makes zero HTTP calls on the second identical call
@patch("requests.post")
def test_cache_hit_makes_zero_http_calls_on_second_call(mock_post, tmp_path):
    mock_post.return_value = _mock_response(
        200,
        json_data={"choices": [{"message": {"content": "cached result"}}]}
    )

    client = LLMClient(api_key="dummy", cache_dir=str(tmp_path))
    call1 = client.chat([{"role": "user", "content": "cache me"}])
    assert call1 == "cached result"
    assert mock_post.call_count == 1

    # Second call
    call2 = client.chat([{"role": "user", "content": "cache me"}])
    assert call2 == "cached result"
    assert mock_post.call_count == 1


# 8. API key never appears in logs or exception messages
@patch("requests.post")
def test_api_key_never_appears_in_logs_or_exceptions(mock_post, tmp_path, caplog):
    secret_key = "AIzaSySecretApiKey123456789"
    mock_post.return_value = _mock_response(
        400,
        text=f"Invalid request with key={secret_key} unauthorized"
    )

    client = LLMClient(api_key=secret_key, cache_dir=str(tmp_path))
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(LLMError) as exc_info:
            client.chat([{"role": "user", "content": "secret test"}])

    # Check exception message
    assert secret_key not in str(exc_info.value)
    assert "[REDACTED_API_KEY]" in str(exc_info.value)

    # Check captured logs
    assert secret_key not in caplog.text
