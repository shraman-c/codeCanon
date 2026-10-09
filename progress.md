# Stage 0 results

- **Exact working model ID(s):** `gemma-4-31b-it` (Verified in Gemini API changelog/pricing docs).
- **Base URL:** `https://generativelanguage.googleapis.com/v1beta/openai/`
- **JSON mode:** Scripts created to test (will fail without API key). Requires testing to determine `response_format` compatibility.
- **System role:** Scripts created to test (will fail without API key). Requires testing to determine `DRIFT_FOLD_SYSTEM` value.
- **Image input:** Scripts created to test OpenAI compat and native endpoints. Needs API key to run and see if native adapter is needed.
- **Ollama tag:** `gemma4:e4b`
- **Ollama pull command:** `ollama pull gemma4:e4b`
- **Failures:** All Gemini API requests return `401 Unauthorized` / `API key not valid` because `.env` currently has an empty `DRIFT_API_KEY`. Please populate `.env` with a valid key and re-run the smoke tests. Ollama skipped because it is not installed/running.
