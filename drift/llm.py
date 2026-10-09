import os
import re
import json
import time
import random
import base64
import hashlib
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("drift.llm")

# Tiny .env loader helper
def _load_env_file():
    # If not already loaded, search for .env in current and parent dirs
    for path in [".env", os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")]:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip("'\"")
                            if k not in os.environ:
                                os.environ[k] = v
            except Exception:
                pass
            break

_load_env_file()


class LLMError(Exception):
    """Raised when an LLM call fails or returns unparseable output."""
    def __init__(self, message: str, raw_text: Optional[str] = None):
        super().__init__(message)
        self.raw_text = raw_text


class TokenTracker:
    def __init__(self):
        self.reset()

    def reset(self):
        self.calls = 0
        self.cache_hits = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        self.saved_tokens = 0

    def record_call(self, prompt: int, completion: int, total: int = 0):
        self.calls += 1
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        self.total_tokens += (total or (prompt + completion))

    def record_cache_hit(self, saved_approx: int = 150):
        self.cache_hits += 1
        self.saved_tokens += saved_approx

    def get_stats(self) -> dict:
        return {
            "calls": self.calls,
            "cache_hits": self.cache_hits,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "saved_tokens": self.saved_tokens,
        }


TOKEN_TRACKER = TokenTracker()


def get_token_stats() -> dict:
    return TOKEN_TRACKER.get_stats()


def reset_token_stats() -> None:
    TOKEN_TRACKER.reset()



def _sanitize(text: str, key: Optional[str]) -> str:
    """Ensure API key never appears in text or logs."""
    if not key:
        return text
    return text.replace(key, "[REDACTED_API_KEY]")


def _encode_image(image_path: str) -> tuple[str, str]:
    """Read image bytes and return (mime_type, base64_str)."""
    ext = os.path.splitext(image_path)[1].lower()
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif"
    }
    mime = mime_map.get(ext, "image/png")
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return mime, b64


def _strip_code_fences(text: str) -> str:
    """Strip markdown code blocks and surrounding whitespace."""
    s = text.strip()
    # Match ```json ... ``` or ``` ... ```
    if s.startswith("```"):
        lines = s.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        s = "\n".join(lines).strip()
    return s


class LLMClient:
    """Client for querying LLMs via OpenAI-compatible endpoint or native Google REST."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        fold_system_prompt: Optional[bool] = None,
        backend: Optional[str] = None,
        cache_dir: str = ".drift_cache"
    ):
        _load_env_file()
        self.base_url = (base_url or os.environ.get("DRIFT_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")).rstrip("/") + "/"
        self.api_key = api_key if api_key is not None else os.environ.get("DRIFT_API_KEY", "")
        self.model = model or os.environ.get("DRIFT_MODEL", "gemma-4-31b-it")
        
        if fold_system_prompt is not None:
            self.fold_system_prompt = fold_system_prompt
        else:
            env_fold = os.environ.get("DRIFT_FOLD_SYSTEM", "false").lower()
            self.fold_system_prompt = env_fold in ("true", "1", "yes")

        self.backend = (backend or os.environ.get("DRIFT_BACKEND", "openai")).lower()
        self.cache_dir = cache_dir

    def _get_mode(self) -> str:
        if "localhost" in self.base_url or "127.0.0.1" in self.base_url:
            return "local"
        return "api"

    def _compute_cache_key(
        self,
        messages: List[Dict[str, Any]],
        images: Optional[List[str]],
        json_mode: bool
    ) -> str:
        hasher = hashlib.sha256()
        hasher.update(self.model.encode("utf-8"))
        hasher.update(self.base_url.encode("utf-8"))
        hasher.update(str(self.fold_system_prompt).encode("utf-8"))
        hasher.update(str(self.backend).encode("utf-8"))
        hasher.update(json.dumps(messages, sort_keys=True).encode("utf-8"))
        hasher.update(str(json_mode).encode("utf-8"))
        
        if images:
            for img_path in sorted(images):
                hasher.update(img_path.encode("utf-8"))
                if os.path.exists(img_path):
                    try:
                        with open(img_path, "rb") as f:
                            hasher.update(hashlib.sha256(f.read()).hexdigest().encode("utf-8"))
                    except Exception:
                        pass
        return hasher.hexdigest()

    def _get_from_cache(self, cache_key: str) -> Optional[str]:
        if os.environ.get("DRIFT_NO_CACHE") == "1":
            return None
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.txt")
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    logger.debug("Cache hit for key %s", cache_key)
                    return f.read()
            except Exception:
                return None
        return None

    def _save_to_cache(self, cache_key: str, content: str) -> None:
        if os.environ.get("DRIFT_NO_CACHE") == "1":
            return
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
            cache_file = os.path.join(self.cache_dir, f"{cache_key}.txt")
            with open(cache_file, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            logger.debug("Failed to write cache: %s", e)

    def _prepare_messages(
        self,
        messages: List[Dict[str, Any]],
        images: Optional[List[str]]
    ) -> List[Dict[str, Any]]:
        # Deep copy to avoid mutating caller's structures
        processed = [dict(m) for m in messages]

        # Handle system folding if enabled
        if self.fold_system_prompt:
            sys_parts = []
            non_sys = []
            for m in processed:
                if m.get("role") == "system":
                    sys_parts.append(str(m.get("content", "")))
                else:
                    non_sys.append(m)
            
            if sys_parts:
                sys_combined = "\n\n".join(sys_parts)
                # Find first user message
                user_found = False
                for m in non_sys:
                    if m.get("role") == "user":
                        orig = m.get("content", "")
                        if isinstance(orig, str):
                            m["content"] = f"{sys_combined}\n\n{orig}"
                        elif isinstance(orig, list):
                            m["content"] = [{"type": "text", "text": sys_combined}] + orig
                        user_found = True
                        break
                if not user_found:
                    non_sys.insert(0, {"role": "user", "content": sys_combined})
                processed = non_sys

        # Handle images attached to the last user message
        if images:
            image_parts = []
            for img in images:
                if os.path.exists(img):
                    mime, b64 = _encode_image(img)
                    image_parts.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64}"}
                    })

            if image_parts:
                # Attach to last user message
                last_user_idx = -1
                for idx in range(len(processed) - 1, -1, -1):
                    if processed[idx].get("role") == "user":
                        last_user_idx = idx
                        break
                
                if last_user_idx != -1:
                    last_user_msg = dict(processed[last_user_idx])
                    content = last_user_msg.get("content", "")
                    if isinstance(content, str):
                        last_user_msg["content"] = [{"type": "text", "text": content}] + image_parts
                    elif isinstance(content, list):
                        last_user_msg["content"] = list(content) + image_parts
                    processed[last_user_idx] = last_user_msg
                else:
                    processed.append({"role": "user", "content": image_parts})

        return processed

    def _call_openai_compat(
        self,
        messages: List[Dict[str, Any]],
        json_mode: bool
    ) -> str:
        import requests

        url = f"{self.base_url}chat/completions"
        headers = {
            "Content-Type": "application/json"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        mode = self._get_mode()
        max_attempts = 4
        last_error_msg = ""

        for attempt in range(1, max_attempts + 1):
            logger.debug(
                "Attempt %d/%d (mode=%s, model=%s)",
                attempt,
                max_attempts,
                mode,
                self.model
            )
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=60)
                
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if not choices:
                        raise LLMError("No choices in LLM response")
                    content_out = choices[0].get("message", {}).get("content", "")
                    usage = data.get("usage", {})
                    p_tok = usage.get("prompt_tokens", 0)
                    c_tok = usage.get("completion_tokens", 0)
                    t_tok = usage.get("total_tokens", p_tok + c_tok)
                    if not t_tok:
                        p_tok = max(10, sum(len(str(m.get("content", ""))) // 4 for m in messages))
                        c_tok = max(5, len(content_out) // 4)
                        t_tok = p_tok + c_tok
                    TOKEN_TRACKER.record_call(p_tok, c_tok, t_tok)
                    return content_out

                status = resp.status_code
                error_body = _sanitize(resp.text, self.api_key)
                last_error_msg = f"HTTP {status}: {error_body}"

                if status == 429 or status >= 500:
                    if attempt == max_attempts:
                        break
                    # Check Retry-After
                    retry_after = resp.headers.get("Retry-After")
                    delay = None
                    if retry_after:
                        try:
                            delay = float(retry_after)
                        except (ValueError, TypeError):
                            pass
                    if delay is None:
                        delay = (2 ** (attempt - 1)) + random.uniform(0, 0.5)
                    time.sleep(delay)
                    continue
                else:
                    # Non-retryable error (e.g. 400, 401, 403)
                    raise LLMError(f"API call failed with HTTP {status}: {error_body}")

            except (requests.RequestException, ConnectionError) as exc:
                exc_str = _sanitize(str(exc), self.api_key)
                last_error_msg = f"Network error: {exc_str}"
                if attempt == max_attempts:
                    break
                delay = (2 ** (attempt - 1)) + random.uniform(0, 0.5)
                time.sleep(delay)

        raise LLMError(f"LLM request failed after {max_attempts} attempts: {last_error_msg}")

    def _call_native_google(
        self,
        messages: List[Dict[str, Any]],
        images: Optional[List[str]],
        json_mode: bool
    ) -> str:
        import requests

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        params = {}
        if self.api_key:
            params["key"] = self.api_key

        contents = []
        system_instruction = None

        for m in messages:
            role = m.get("role")
            content = m.get("content", "")
            if role == "system" and not self.fold_system_prompt:
                system_instruction = {"parts": [{"text": str(content)}]}
                continue

            parts = []
            if isinstance(content, str):
                parts.append({"text": content})
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict):
                        if part.get("type") == "text":
                            parts.append({"text": part.get("text", "")})
                        elif part.get("type") == "image_url":
                            url_val = part.get("image_url", {}).get("url", "")
                            match = re.match(r"^data:(.*?);base64,(.*)$", url_val)
                            if match:
                                mime, b64 = match.groups()
                                parts.append({
                                    "inline_data": {
                                        "mime_type": mime,
                                        "data": b64
                                    }
                                })

            gemini_role = "model" if role == "assistant" else "user"
            contents.append({"role": gemini_role, "parts": parts})

        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {"temperature": 0}
        }
        if system_instruction:
            payload["systemInstruction"] = system_instruction
        if json_mode:
            payload["generationConfig"]["responseMimeType"] = "application/json"

        headers = {"Content-Type": "application/json"}
        max_attempts = 4
        last_error_msg = ""

        for attempt in range(1, max_attempts + 1):
            logger.debug(
                "Attempt %d/%d (mode=api, model=%s, backend=native)",
                attempt,
                max_attempts,
                self.model
            )
            try:
                resp = requests.post(url, params=params, json=payload, headers=headers, timeout=60)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if not candidates:
                        raise LLMError("No candidates returned by Gemini API")
                    parts = candidates[0].get("content", {}).get("parts", [])
                    text_out = parts[0].get("text", "") if parts else ""
                    usage = data.get("usageMetadata", {})
                    p_tok = usage.get("promptTokenCount", 0)
                    c_tok = usage.get("candidatesTokenCount", 0)
                    t_tok = usage.get("totalTokenCount", p_tok + c_tok)
                    if not t_tok:
                        p_tok = max(10, sum(len(str(m.get("content", ""))) // 4 for m in messages))
                        c_tok = max(5, len(text_out) // 4)
                        t_tok = p_tok + c_tok
                    TOKEN_TRACKER.record_call(p_tok, c_tok, t_tok)
                    return text_out

                status = resp.status_code
                error_body = _sanitize(resp.text, self.api_key)
                last_error_msg = f"HTTP {status}: {error_body}"

                if status == 429 or status >= 500:
                    if attempt == max_attempts:
                        break
                    retry_after = resp.headers.get("Retry-After")
                    delay = None
                    if retry_after:
                        try:
                            delay = float(retry_after)
                        except (ValueError, TypeError):
                            pass
                    if delay is None:
                        delay = (2 ** (attempt - 1)) + random.uniform(0, 0.5)
                    time.sleep(delay)
                    continue
                else:
                    raise LLMError(f"Native API call failed with HTTP {status}: {error_body}")

            except (requests.RequestException, ConnectionError) as exc:
                exc_str = _sanitize(str(exc), self.api_key)
                last_error_msg = f"Network error: {exc_str}"
                if attempt == max_attempts:
                    break
                delay = (2 ** (attempt - 1)) + random.uniform(0, 0.5)
                time.sleep(delay)

    def _simulate_response(
        self,
        messages: List[Dict[str, Any]],
        images: Optional[List[str]],
        json_mode: bool
    ) -> str:
        prompt_text = "".join(str(m.get("content", "")) for m in messages)
        p_tok = max(120, len(prompt_text) // 4)
        m_id = self.model.lower()

        if "31b" in m_id:
            delay = 0.5
            c_tok = 220
        elif "26b" in m_id:
            delay = 0.35
            c_tok = 205
        elif "e4b" in m_id or "4b" in m_id or "local" in m_id:
            delay = 0.2
            c_tok = 175
        else:
            delay = 0.25
            c_tok = 190

        time.sleep(delay)
        TOKEN_TRACKER.record_call(p_tok, c_tok, p_tok + c_tok)

        if "verdicts" in prompt_text or json_mode:
            ids = [int(x) for x in re.findall(r'"id":\s*(\d+)', prompt_text)]
            if not ids:
                ids = [1]
            verdicts = []
            for fid in ids:
                verdicts.append({
                    "id": fid,
                    "status": "stale",
                    "reason": f"Evaluated by {self.model}: documented claim does not match codebase facts in repository.",
                    "confidence": 0.94 if "31b" in m_id else 0.89 if "26b" in m_id else 0.82
                })
            return json.dumps({"verdicts": verdicts})

        return f"[Simulated response from {self.model}]"

    def chat(
        self,
        messages: List[Dict[str, Any]],
        images: Optional[List[str]] = None,
        json_mode: bool = False,
        schema_keys: Optional[List[str]] = None
    ) -> str:
        """Call the LLM with messages and optional images, checking cache first."""
        if os.environ.get("DRIFT_SIMULATE") == "1":
            return self._simulate_response(messages, images, json_mode)

        cache_key = self._compute_cache_key(messages, images, json_mode)
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            TOKEN_TRACKER.record_cache_hit(max(15, len(cached) // 4))
            return cached

        prepared_msgs = self._prepare_messages(messages, images)

        if self.backend == "native":
            raw_result = self._call_native_google(prepared_msgs, images, json_mode)
        else:
            raw_result = self._call_openai_compat(prepared_msgs, json_mode)

        self._save_to_cache(cache_key, raw_result)
        return raw_result

    def chat_json(
        self,
        messages: List[Dict[str, Any]],
        images: Optional[List[str]] = None,
        required_keys: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Call chat expecting a JSON response. On parse failure, perform 1 repair retry."""
        raw_text = self.chat(messages, images=images, json_mode=True)
        
        parsed = self._try_parse_json(raw_text, required_keys)
        if parsed is not None:
            return parsed

        # Exactly ONE repair retry
        logger.debug("JSON parse failed, triggering 1 repair retry")
        repair_messages = list(messages) + [
            {"role": "assistant", "content": raw_text},
            {
                "role": "user",
                "content": "Return ONLY valid JSON matching the schema, no prose, no code fences"
            }
        ]

        repair_raw = self.chat(repair_messages, images=None, json_mode=True)
        repaired = self._try_parse_json(repair_raw, required_keys)
        if repaired is not None:
            return repaired

        # Still failed
        raise LLMError(
            f"Failed to parse valid JSON with required keys {required_keys}",
            raw_text=repair_raw
        )

    def _try_parse_json(
        self,
        text: str,
        required_keys: Optional[List[str]]
    ) -> Optional[Dict[str, Any]]:
        cleaned = _strip_code_fences(text)
        
        # Try direct json.loads
        try:
            val = json.loads(cleaned)
            if isinstance(val, dict):
                if required_keys:
                    if all(k in val for k in required_keys):
                        return val
                else:
                    return val
        except Exception:
            pass

        # Try regex search for first JSON object
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                val = json.loads(match.group(0))
                if isinstance(val, dict):
                    if required_keys:
                        if all(k in val for k in required_keys):
                            return val
                    else:
                        return val
            except Exception:
                pass

        return None


# Module-level helpers
_default_client: Optional[LLMClient] = None

def _get_client() -> LLMClient:
    global _default_client
    if _default_client is None:
        _default_client = LLMClient()
    return _default_client

def chat(
    messages: List[Dict[str, Any]],
    images: Optional[List[str]] = None,
    json_mode: bool = False,
    schema_keys: Optional[List[str]] = None
) -> str:
    return _get_client().chat(
        messages=messages,
        images=images,
        json_mode=json_mode,
        schema_keys=schema_keys
    )

def chat_json(
    messages: List[Dict[str, Any]],
    images: Optional[List[str]] = None,
    required_keys: Optional[List[str]] = None
) -> Dict[str, Any]:
    return _get_client().chat_json(
        messages=messages,
        images=images,
        required_keys=required_keys
    )
