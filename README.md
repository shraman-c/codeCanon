<img width="1507" height="815" alt="codeCanon" src="https://github.com/user-attachments/assets/acb71ee5-6104-41e1-b8c8-2629afc179f1" />

# codeCanon: Docs-Drift-Detector

Code evolves fast. API routes get renamed, environment variables change prefixes, and ports shift. But `README.md` files, API docs, and embedded terminal screenshots get left behind. This causes friction, broken tutorials, and hours of wasted developer time.

**codeCanon** is a CLI tool, GUI, and autonomous Agent Skill that mathematically proves whether your documentation matches your JS/TS codebase. 

## Features
- **Deterministic Code Fact Extraction**: Lightning-fast AST and Regex parsing to extract code facts (Next.js/Express routes, `package.json` scripts, `.env` variables, ports, and Node engine versions).
- **Two-Layer Engine**: Runs a deterministic matcher first (to flag `OK` and `STALE` claims instantly) and only escalates ambiguous/fuzzy matches (`SUSPECT`) to the AI Judge to save time and API costs.
- **Multimodal Screenshot Verification**: Uses Gemma 4 Vision to read local terminal/UI images referenced in your Markdown, extracting text and commands to verify if your tutorial screenshots are outdated.
- **Automated Remediation**: When the Gemma 4 Judge confirms a piece of documentation is drifting, it generates a deterministic, unified `git apply` patch to fix your markdown files.
- **Desktop GUI**: Includes a local Tkinter GUI (`scripts/gui.py`) with a beautiful terminal output streamer.

## Supported Stacks
- **Next.js** (App Router & Pages Router)
- **Express.js** API Servers
- **Vite / React** Apps

## Why Gemma 4?
This project relies on the **Gemma 4** family of models for two critical reasons:
1. **Multimodal Excellence:** Gemma 4's vision capabilities are used to read and extract precise terminal commands and UI text from embedded screenshots in documentation.
2. **Flexible Deployment:** We support the frontier `gemma-4-31b-it` via the Gemini API for complex batched reasoning, but we also fully support the edge-quantized `gemma4:e4b` model via Ollama for users who want to run documentation drift scans entirely offline and locally for extreme privacy.

## Installation & Setup
1. Clone the repository.
2. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```
3. Add your Gemini API key to `.env` as `DRIFT_API_KEY` (or uncomment the Ollama local config inside `.env`).

## Usage

### 1. Graphical Interface (GUI)
Run the desktop app for a visual drift dashboard:
```bash
python scripts/gui.py
```

### 2. Command Line (CLI)
Scan any local web repository:
```bash
python scripts/drift.py scan /path/to/your/web/repo
```
*Optional Flags:*
- `--no-llm`: Skip the Gemma 4 judge and multimodal vision (runs instantly in deterministic mode only).
- `--no-images`: Skip scanning screenshots.

### 3. Benchmark Suite
You can verify the accuracy of the detection engine by running our ground-truth benchmark suite (which tests planted drifts against decoys):
```bash
python benchmark/run_bench.py --model gemma-4-31b-it
```

## Architecture Map
- `scripts/drift.py` / `scripts/gui.py`: Entrypoints
- `drift/extract_*.py`: Code & AST Fact Extractors
- `drift/match.py`: Deterministic Matcher
- `drift/llm.py` & `drift/vision.py`: Gemma 4 AI Clients
- `drift/judge.py` & `drift/patch.py`: Verdict & Auto-Patch Generation
