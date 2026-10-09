---
name: docs-drift-detector
description: Detects documentation drift in JavaScript/TypeScript web projects (Next.js, Express, Vite/React): stale npm scripts, env vars, API routes, ports, Node versions, dependencies, code samples, and screenshots in README/docs, and proposes patches. Powered by Gemma 4 via Gemini API or local Ollama.
---

# Instructions

1. **Set Environment Variables:**
   Configure `DRIFT_BASE_URL`, `DRIFT_API_KEY`, `DRIFT_MODEL` (default: `gemma-4-31b-it`), and `DRIFT_FOLD_SYSTEM` in your `.env` or system environment. For offline/local runs, configure Ollama (`http://localhost:11434/v1`, tag `gemma4:e4b`).

2. **Execute Drift Scanner:**
   Run the CLI scanner against the target JS/TS repository:
   ```bash
   python scripts/drift.py scan <repo_path>
   ```
   *(TODO: CLI `scripts/drift.py` integration planned for Stage 3)*

3. **Inspect Drift Findings:**
   Read and review the generated output file `drift-report.json`. Check each `STALE` and `SUSPECT` finding, verifying the cited code fact and proposed replacement text.
   *(TODO: JSON + Markdown reporter `drift/report.py` planned for Stage 3)*

4. **Apply Patches:**
   Review proposed unified diffs and apply patches with `git apply` only after explicit user confirmation:
   ```bash
   git apply patch.diff
   ```
   *(TODO: Deterministic patch generator `drift/patch.py` planned for Stage 2)*
