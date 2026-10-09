---
name: docs-drift-detector
description: Detects documentation drift in JavaScript/TypeScript web repositories (Next.js, Express, Vite/React): identifies stale npm scripts, env vars, API routes, ports, runtime engines, and screenshots in documentation, and generates verified unified diff patches. Powered by Gemma 4 via Gemini API or local Ollama. Use after codebase refactors or before releases.
---

# docs-drift-detector

An Agent Skill that identifies discrepancies between actual JavaScript/TypeScript code facts and documentation assertions (Markdown guides, README files, and terminal/UI screenshots). Powered by **Gemma 4** (`gemma-4-31b-it` via Gemini API or `gemma4:e4b` via local Ollama).

## Setup & Environment

Configure the required `DRIFT_*` environment variables in your `.env` (git-ignored) or environment:

```bash
# Gemini API (OpenAI-compatible endpoint)
DRIFT_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
DRIFT_API_KEY=
DRIFT_MODEL=gemma-4-31b-it
DRIFT_FOLD_SYSTEM=false

# Optional fallback or local offline mode (Ollama)
# DRIFT_BASE_URL=http://localhost:11434/v1
# DRIFT_MODEL=gemma4:e4b

# Tuning parameters
DRIFT_JUDGE_THRESHOLD=0.6
```

## Instructions

When instructed to detect documentation drift in a web repository, follow these steps:

1. **Verify Environment Configuration:**
   Ensure `DRIFT_BASE_URL` and `DRIFT_API_KEY` (or local Ollama endpoint) are set in the environment.

2. **Execute Drift Scanner:**
   Run the CLI entrypoint against the target web repository using relative script paths:
   ```bash
   python scripts/drift.py scan <repo_path>
   ```
   *Options:*
   - `--no-llm`: Run deterministic matching only (skip LLM judging).
   - `--no-images`: Skip multimodal vision extraction from screenshots.
   - `--output-dir <path>`: Specify destination for report files.

3. **Inspect Generated Reports:**
   Review the resulting findings in `drift-report.json` and `drift-report.md`:
   - `OK`: Claim matches current codebase facts.
   - `SUSPECT`: Potential discrepancy requiring review.
   - `STALE`: Proven drift between code and documentation.
   - Image findings indicate outdated screenshots with the exact detected quote and replacement code fact.

4. **Review & Apply Patches:**
   Each `STALE` text finding includes a proposed unified diff pre-verified with `git apply --check`.
   Review the unified diff in `drift-report.md` or `drift-report.json`, and apply with `git apply` only after user confirmation:
   ```bash
   git apply drift-patch.diff
   ```
