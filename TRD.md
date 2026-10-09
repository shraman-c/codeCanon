# TRD — docs-drift-detector (Web Dev Edition)

Target: JS/TS web repos (Next.js, Express, Vite/React). The tool itself is written in Python (stdlib plus a few small packages) and analyses repos by reading files, so it needs no JS runtime, except the optional `node --check` sample validation.

## 1. Architecture Overview

```
                 ┌────────────────────────────────────────────┐
  Agent / CLI →  │  SKILL.md  →  scripts/drift.py (entrypoint) │
                 └───────────────────┬────────────────────────┘
                                     │
   ┌─────────────────────────────────┼──────────────────────────────┐
   ▼                                 ▼                              ▼
 [A] Web Fact Extractors       [B] Doc Claim Extractor        [C] LLM Judge + Patcher
 pkg · env · routes · ports    (Markdown, web-aware)          (OpenAI-compatible client)
 components (P1)                     │                              ▲
   │                                 ▼                              │
   └──────────► [B] Matcher (deterministic, per-kind rules) ────────┘
                         │  OK / STALE / SUSPECT
                         ▼
               [C] Patch generator → [B] Reporter (JSON + Markdown)
```

## 2. Repository Layout
See `structure.md`.

## 3. Data Models

```python
@dataclass
class Fact:             # something that exists in the web repo
    kind: str           # "npm_script" | "env_var" | "route" | "port" | "engine"
                        # | "dependency" | "component_prop"
    name: str           # "dev", "DATABASE_URL", "GET /api/users", "3000", "node", "prisma"
    detail: str         # "next dev -p 3000", ">=20", "^5.2.0", "props: {variant,size}"
    file: str
    line: int

@dataclass
class Claim:            # something the docs assert
    kind: str           # same kinds + "code_sample"
    text: str           # "npm run dev:local", "GET /api/users", "Node 16+", "localhost:3000"
    doc_file: str
    line: int
    context: str        # surrounding paragraph (≤ 400 chars)

@dataclass
class Finding:
    claim: Claim
    status: str         # "OK" | "STALE" | "SUSPECT"
    reason: str
    evidence: list[Fact]
    confidence: float
    patch: str | None
    source: str         # "deterministic" | "llm"
```

## 4. Fact Extractors (Member A)

| Module | Kind | How |
|---|---|---|
| `extract_pkg.py` | `npm_script`, `dependency`, `engine` | `json.load(package.json)`; also `.nvmrc`; detect package manager from lockfile |
| `extract_env.py` | `env_var` | Regex over `*.{js,jsx,ts,tsx,mjs}`: `process.env.X`, `process.env["X"]`, `import.meta.env.X`; plus keys in `.env.example`. Tag `NEXT_PUBLIC_*`/`VITE_*` as client-exposed |
| `extract_routes.py` | `route` | **Next App Router:** each `app/**/route.{ts,js}` → URL from folder path (`[id]`→`:id`, ignore `(group)` folders), methods from `export async function GET/POST…`. **Pages Router:** `pages/api/**` → `/api/...`. **Express:** regex for `(app\|router)\.(get\|post\|put\|patch\|delete)\(['"`]/…` plus `app.use('/prefix', router)` prefix resolution when the router is in the same file or an obvious import |
| `extract_ports.py` | `port` | `listen(\d+)`, `PORT \|\| \d+`, `-p \d+`/`--port \d+` in package.json scripts, vite `server: { port }` |
| `extract_components.py` (P1) | `component_prop` | Regex/TS-lite: exported function components and their destructured props or `interface XProps { … }` |
| `gitdiff.py` | — | `git diff base..head`; re-extract facts at both revisions; set of removed/renamed/changed facts |

Skip: `node_modules`, `.next`, `dist`, `build`, `.git`, `coverage`, test files (configurable).

## 5. Doc Claim Extractor (Member B) — `extract_docs.py`

Markdown parsed with `markdown-it-py` (or a line scanner fallback). Claim patterns:

| Kind | Pattern |
|---|---|
| `npm_script` | `(npm run\|pnpm( run)?\|yarn( run)?\|bun( run)?) <name>` in code spans and bash blocks |
| `env_var` | `UPPER_SNAKE` tokens inside code spans, `.env` snippets, "set X" sentences |
| `route` | `(GET\|POST\|PUT\|PATCH\|DELETE) /path`, `curl …/path`, `fetch('/api/…')` in samples, `/api/...` in code spans |
| `port` | `localhost:\d+`, `port \d+`, `:\d{4}` in URLs |
| `engine` | `Node(\.js)? v?\d+(\+\|\.x)?`, `npm \d+`, "requires Node …" |
| `dependency` | known package names in code spans or "built with / uses X" lines (from a lookup of names in package.json plus an allow-list of popular web libs) |
| `code_sample` | fenced js/ts/jsx/tsx blocks: collect import specifiers; flag relative imports; run `node --check` for js |

Each claim keeps ±1 paragraph of context.

## 6. Matcher (Member B) — `match.py`

Rules by kind. All comparisons are normalised (case, quotes, trailing slash).

| Kind | OK | SUSPECT | STALE |
|---|---|---|---|
| `npm_script` | name in `scripts` (or built-in `start`/`test`/`install`/`ci` fallbacks) | fuzzy match ≥ 0.8 (e.g. `dev:local` vs `dev`) | no match |
| `env_var` | present in code or `.env.example` | fuzzy match, or only present with different prefix (`API_URL` vs `NEXT_PUBLIC_API_URL`) | absent everywhere (allow-list: `NODE_ENV`, `PORT`, `HOME`, `PATH`, `CI`) |
| `route` | path+method present (dynamic segments normalised: `:id` = `[id]` = `{id}`) | path present but method differs, or similar path/prefix differs (`/api/users` vs `/api/v2/users`) | no similar route |
| `port` | matches a detected port | multiple ports detected, ambiguous | docs port absent from all detected ports |
| `engine` | docs version satisfies `engines`/`.nvmrc` | docs version lower than engines minimum, or vague | no engines info → `OK` (skip) |
| `dependency` | in dependencies | version/major mismatch ("Tailwind v3" vs ^4) | package mentioned as used but not in dependencies |
| `code_sample` | imports resolve | import path resolves to different casing/extension | relative import target missing; package not in dependencies; syntax error |

Generic allow-list: `--help`, `--version`, `localhost`, placeholder tokens like `YOUR_API_KEY`, `<your-...>`, `xxx`.

## 7. LLM Judge (Member C) — `judge.py`, `llm.py`

- Only `SUSPECT` findings are sent; batched up to 5 per call.
- Prompt contains: claim text and context, the candidate facts (kind, name, detail, file:line). The model must answer in JSON:
```json
{"verdicts":[{"id":1,"status":"stale|ok","reason":"...","corrected_text":"...","confidence":0.0}]}
```
- Guardrails: `temperature=0`, JSON-only system prompt, schema validation, one repair retry, drop verdicts below the confidence threshold (default 0.6), require the model to cite which fact it relied on.
- Content-hash cache in `.drift_cache/`.
- Web-specific prompt hints: route normalisation (`[id]`, `:id`), `NEXT_PUBLIC_` and `VITE_` prefix semantics, package-manager equivalence (`npm run dev` ≈ `pnpm dev`).

## 8. Patch Generator (Member C) — `patch.py`

- For `STALE`/`stale` findings with a `corrected_text` (deterministic suggestion or LLM-provided), replace the exact span on the doc line and emit a unified diff with `difflib`.
- Deterministic suggestions: closest script/env var/route name from evidence when similarity is high.
- Verify with `git apply --check`. If unsure, output `patch: null` plus "needs human review".

## 9. Reporter (Member B) — `report.py`

`drift-report.json` (schema in `references/schema.json`) and `drift-report.md`. Exit code `1` if any STALE finding (CI-friendly). Summary grouped by doc file and by kind.

## 10. Model Recommendation (open-weight)

> Model IDs and free-tier limits change often. Check each provider's catalog before the event and note the exact ID in `progress.md`.

| Role | Model | Why |
|---|---|---|
| **Primary (hosted)** | `gpt-oss-120b` (Apache-2.0) or `Llama 3.3 70B Instruct` | Strong instruction-following and JSON output; fast on Groq |
| **Code/web-aware alternative** | `Qwen3-Coder` / `Qwen2.5-Coder-32B-Instruct` (Apache-2.0) | Strong at JS/TS and config reading |
| **Fallback** | Same model on a second provider, or `Llama 3.1 8B` | When the primary is rate-limited |
| **Local / offline** | `qwen2.5-coder:7b` via Ollama | Zero data egress; privacy demo |

Default: `gpt-oss-120b` on Groq, fallback `Qwen2.5-Coder-32B` on OpenRouter or Together, local `qwen2.5-coder:7b`. Check each model card's license and cite it in the README.

### API keys
| Provider | Where | Notes |
|---|---|---|
| Groq | console.groq.com → API Keys | Very fast; free tier with limits |
| OpenRouter | openrouter.ai/keys | One key for many open-weight models; some `:free` variants |
| Together AI | api.together.ai → Settings → API Keys | Wide open-weight catalog |
| Hugging Face | huggingface.co/settings/tokens | Inference providers |
| NVIDIA NIM | build.nvidia.com | Free trial credits |
| Ollama | ollama.com | No key; `ollama pull qwen2.5-coder:7b` |

Create keys before the build starts. Keep them in `.env` (git-ignored); commit only `.env.example`.

```
DRIFT_BASE_URL=https://api.groq.com/openai/v1
DRIFT_API_KEY=...
DRIFT_MODEL=openai/gpt-oss-120b
```
Any OpenAI-compatible endpoint works (Groq, OpenRouter, Together, Ollama at `http://localhost:11434/v1`).

## 11. App Flow

```
1. Invoke    → python scripts/drift.py scan <web-repo> [--diff main..HEAD] [--no-llm]
2. Detect    → confirm web project (package.json present; detect Next / Express / Vite)
3. Discover  → source files + markdown docs (respect ignores)
4. Extract   → facts (A: pkg, env, routes, ports, components) ∥ claims (B: docs)
5. Narrow    → (diff mode) keep only claims touching changed facts
6. Match     → per-kind deterministic rules → OK / STALE / SUSPECT
7. Judge     → SUSPECT → batched open-weight LLM calls → validated verdicts (cached)
8. Patch     → corrected text → unified diff → git apply --check
9. Report    → drift-report.json + drift-report.md + exit code
10. Agent    → reads JSON, applies patches or asks the user to approve
```

If no `package.json` is found, the skill exits with a clear "not a web project" message.

## 12. `SKILL.md` Requirements

```markdown
---
name: docs-drift-detector
description: Detects documentation drift in JavaScript/TypeScript web projects (Next.js, Express, Vite/React): stale npm scripts, env vars, API routes, ports, Node versions, dependencies and code samples in README/docs, and proposes patches. Use after code changes or before releases.
---
# Instructions
1. Run `python scripts/drift.py scan <repo> [--diff base..head]`
2. Read `drift-report.json`; review each STALE finding and its patch
3. Apply with `git apply` after user confirmation
```
Validate: folder name equals `name`, frontmatter valid, concise instructions, relative script paths. Re-read the official Agent Skill spec at the start and re-validate in the last hour.

## 13. Testing Strategy

| Layer | What | Owner |
|---|---|---|
| Unit — pkg/env/routes/ports extractors | Next, Express, Vite fixtures | A |
| Unit — doc parser and matcher | edge cases, allow-list, dynamic-route normalisation, fuzzy match | B |
| Unit — LLM client, judge, patcher | mocked responses, malformed JSON, retry | C |
| Integration | full run per fixture | each member, one fixture each |
| Benchmark | planted drift; precision/recall | A runs; B, C verify |
| Real-repo test | one real public web repo each | A (Next.js), B (Express), C (Vite/React) |
| Skill compliance | spec validation plus a fresh-agent run | C builds; A, B cross-check |

**Cross-testing rule:** each member writes tests for their own module, then tries to break another member's: A→B's matcher, B→C's judge and patcher, C→A's extractors.

## 14. Benchmark Design

Three web fixtures, each with ~10 planted drifts and ~4 decoys (things that look like drift but are correct):

| Fixture | Owner | Planted drift examples |
|---|---|---|
| `next_app` (App Router + Prisma) | A | renamed script, route moved to `/api/v2/…`, `NEXT_PUBLIC_` var renamed, Node 16→20, removed Prisma |
| `express_api` | B | removed env var, changed port, method changed GET→POST, router prefix changed, broken import in sample |
| `vite_react` | C | `VITE_` var renamed, script renamed, Tailwind v3→v4 mention, prop renamed, missing component path |

`expected.json` is the ground truth; `run_bench.py` prints precision, recall, calls saved and patch validity, and compares to a naive `grep`-for-names baseline.

## 15. Stages
See `stages.md` for the hour-by-hour plan and per-member tasks.

## 16. Definition of Done

- [ ] Public repo, MIT license from the first commit
- [ ] `SKILL.md` valid under the Agent Skill spec
- [ ] Open-weight default model documented with a model card link
- [ ] `--no-llm`, hosted and local modes all run
- [ ] P0 claim kinds working on all three fixtures
- [ ] Benchmark table in README
- [ ] Demo on a real web repo's older commit
- [ ] Every member has commits and reviewed PRs
- [ ] Fresh-clone install under 3 minutes
- [ ] Submission added before the deadline

## 17. Contingency Plan

| If… | Then… |
|---|---|
| Express prefix resolution is hard | Resolve same-file prefixes only; mark cross-file ones SUSPECT |
| Component props extraction slips | Cut it (P1); keep scripts, env, routes, ports, engines |
| Rate-limited | Switch provider through env vars; use the cache; `--no-llm` for clear-cut claims |
| Patches don't apply cleanly | Emit `corrected_text` with a manual-review flag |
| Behind at 4:00 | Cut diff mode, `.driftrc`, Markdown report |
