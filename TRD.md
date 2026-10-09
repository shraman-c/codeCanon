# TRD — docs-drift-detector (Web Dev Edition, Gemma 4)

Target: JS/TS web repos (Next.js, Express, Vite/React). The tool is written in Python (stdlib plus a few small packages) and reads repos as files. A JS runtime is only needed for the optional `node --check` sample validation. **Gemma 4** is the model for judgement and for reading screenshots.

## 1. Architecture Overview

```
                 ┌────────────────────────────────────────────┐
  Agent / CLI →  │  SKILL.md  →  scripts/drift.py (entrypoint) │
                 └───────────────────┬────────────────────────┘
                                     │
   ┌─────────────────────────────────┼──────────────────────────────┐
   ▼                                 ▼                              ▼
 [A] Web Fact Extractors       [B] Doc Claim Extractors       [C] Gemma 4 Layer
 pkg · env · routes · ports    text (Markdown) + images       llm.py (text + vision)
                                     │  image claims ◄──────  vision.py (image → claims)
   │                                 ▼                              ▲
   └──────────► [B] Matcher (deterministic, per-kind rules) ────────┘
                         │  OK / STALE / SUSPECT
                         ▼
               [C] Judge + Patcher → [B] Reporter (JSON + Markdown)
```

## 2. Repository Layout
See `structure.md`.

## 3. Data Models

```python
@dataclass
class Fact:             # something that exists in the web repo
    kind: str           # "npm_script" | "env_var" | "route" | "port" | "engine"
                        # | "dependency" | "component_prop"
    name: str
    detail: str
    file: str
    line: int

@dataclass
class Claim:            # something the docs assert
    kind: str           # same kinds + "code_sample"
    text: str
    doc_file: str
    line: int
    context: str
    source: str         # "text" | "image"
    image_path: str | None   # set when source == "image"
    extracted_text: str | None  # what the vision model read, for evidence

@dataclass
class Finding:
    claim: Claim
    status: str         # "OK" | "STALE" | "SUSPECT"
    reason: str
    evidence: list[Fact]
    confidence: float
    patch: str | None   # null for image findings (replace the image)
    source: str         # "deterministic" | "llm"
```

## 4. Fact Extractors (Member A)

| Module | Kind | How |
|---|---|---|
| `extract_pkg.py` | `npm_script`, `dependency`, `engine` | `json.load(package.json)`; `.nvmrc`; package manager from lockfile |
| `extract_env.py` | `env_var` | Regex over `*.{js,jsx,ts,tsx,mjs}`: `process.env.X`, `process.env["X"]`, `import.meta.env.X`; plus `.env.example` keys. Tag `NEXT_PUBLIC_*` / `VITE_*` as client-exposed |
| `extract_routes.py` | `route` | **Next App Router:** `app/**/route.{ts,js}` → URL from folders (`[id]`→`:id`, ignore `(group)`), methods from `export async function GET/POST…`. **Pages Router:** `pages/api/**`. **Express:** `(app\|router)\.(get\|post\|put\|patch\|delete)\(['"`]/…` plus same-file `app.use('/prefix', router)` |
| `extract_ports.py` | `port` | `listen(\d+)`, `PORT \|\| \d+`, `-p`/`--port` in scripts, vite `server.port` |
| `extract_components.py` (P2) | `component_prop` | Exported components and props |
| `gitdiff.py` | — | `git diff base..head`; facts at both revisions; removed/renamed/changed set |

Skip: `node_modules`, `.next`, `dist`, `build`, `.git`, `coverage`, test files (configurable).

## 5. Doc Claim Extractors (Member B)

### 5.1 Text — `extract_docs.py`
Markdown parsed with `markdown-it-py` (line-scanner fallback).

| Kind | Pattern |
|---|---|
| `npm_script` | `(npm run\|pnpm( run)?\|yarn( run)?\|bun( run)?) <name>` in code spans and bash blocks |
| `env_var` | `UPPER_SNAKE` tokens in code spans, `.env` snippets |
| `route` | `(GET\|POST\|PUT\|PATCH\|DELETE) /path`, `curl …/path`, `fetch('/api/…')`, `/api/...` in code spans |
| `port` | `localhost:\d+`, `port \d+` |
| `engine` | `Node(\.js)? v?\d+(\+\|\.x)?`, "requires Node …" |
| `dependency` | package names in code spans or "uses X" lines (cross-checked against package.json plus a popular-web-libs list) |
| `code_sample` | fenced js/ts blocks: relative imports, package imports, `node --check` (P1) |

### 5.2 Images — `extract_images.py` (P1, the Gemma 4 feature)
1. Find image references: `![alt](path)` and `<img src="...">` in each doc.
2. Keep local files only (`.png .jpg .jpeg .webp`), under the size cap (default 1.5 MB), at most N images (default 10). Remote URLs skipped and listed in the report.
3. For each image, call `vision.extract_claims(image, doc_context)` (Member C). Prompt asks Gemma 4 to return JSON:
```json
{"image_type":"terminal|env|api|ui|other",
 "claims":[{"kind":"npm_script|env_var|route|port|engine","text":"npm run dev:local","quote":"$ npm run dev:local"}]}
```
4. Convert each extracted claim into a `Claim(source="image", image_path=..., extracted_text=quote)` and pass it through the **same matcher** as text claims.
5. Cache by image hash so reruns cost nothing.

Matching image claims: deterministic rules first (same as text). Anything `SUSPECT` goes to the Gemma judge, which sees the claim plus evidence facts. Image findings never get an auto text patch; the report says which image is outdated, what was read, what the code says, and the suggested replacement text for the caption if any.

## 6. Matcher (Member B) — `match.py`

Per kind. All comparisons normalised (case, quotes, trailing slash).

| Kind | OK | SUSPECT | STALE |
|---|---|---|---|
| `npm_script` | name in `scripts` (or built-in `start`/`test`/`install`/`ci`) | fuzzy ≥ 0.8 (`dev:local` vs `dev`) | no match |
| `env_var` | present in code or `.env.example` | fuzzy, or prefix differs (`API_URL` vs `NEXT_PUBLIC_API_URL`) | absent (allow-list: `NODE_ENV`, `PORT`, `HOME`, `PATH`, `CI`) |
| `route` | path+method present (`:id` = `[id]` = `{id}`) | method differs, or similar path/prefix differs (`/api/users` vs `/api/v2/users`) | no similar route |
| `port` | matches a detected port | several ports detected | port absent from all detected ports |
| `engine` | docs version satisfies `engines`/`.nvmrc` | docs lower than min, or vague | no engines info → `OK` |
| `dependency` | in dependencies | major mismatch ("Tailwind v3" vs ^4) | mentioned as used but absent |
| `code_sample` | imports resolve | casing/extension differs | missing relative import, unknown package, syntax error |

**Image claims** use the same rules but with a confidence discount (OCR/vision noise): a `STALE` image claim is downgraded to `SUSPECT` unless the extracted quote is long and unambiguous.

Allow-list: `--help`, `--version`, `localhost`, placeholder tokens (`YOUR_API_KEY`, `<your-...>`, `xxx`).

## 7. Gemma 4 Layer (Member C)

### 7.1 Model client — `llm.py`
- **OpenAI-compatible client** configured by env vars; works for the Gemini API's OpenAI-compatible endpoint (verify the base URL in the AI Studio docs) and for Ollama. Optional: native Google SDK adapter if the compatibility endpoint lacks a needed feature (image input or JSON mode).
- Supports **text and image messages** (base64 data URL / inline image part).
- `fold_system_prompt` flag: if the model rejects or ignores the system role, prepend the instructions to the user message. Decide in Stage 0.
- `temperature=0`, retry with backoff on 429/5xx, content-hash cache in `.drift_cache/`, JSON schema validation, one repair retry.

### 7.2 Judge — `judge.py`
- Only `SUSPECT` findings, batched up to 5 per call.
- Prompt: claim text and context (and extracted quote for images), candidate facts with file:line. Required output:
```json
{"verdicts":[{"id":1,"status":"stale|ok","reason":"...","corrected_text":"...","confidence":0.0}]}
```
- Drop verdicts below the confidence threshold (default 0.6); require citing which fact was used.
- Web hints in the prompt: route normalisation, `NEXT_PUBLIC_`/`VITE_` semantics, package-manager equivalence.

### 7.3 Vision — `vision.py`
- `extract_claims(image_path, context)`: builds the vision prompt, sends the image, validates the JSON, returns a list of raw claims. Handles "no relevant text" (returns empty list) and low-quality images (returns `image_type: other`).

### 7.4 Patch generator — `patch.py`
- For `STALE`/`stale` **text** findings with `corrected_text`: replace the exact span on the doc line and emit a unified diff with `difflib`; deterministic suggestions use the closest fact name when similarity is high.
- Verify with `git apply --check`. If unsure: `patch: null` and "needs human review".
- For image findings: no patch; report entry only.

## 8. Reporter (Member B) — `report.py`

`drift-report.json` (schema in `references/schema.json`) and `drift-report.md`. Image findings include the image path and the quoted text. Exit code `1` if any STALE finding. Summary grouped by doc file and kind, plus a "model used" line (id and mode: api/local) for benchmark transparency.

## 9. Model Plan (Gemma 4)

> Model IDs, tags and free-tier limits change. Confirm exact IDs in AI Studio and Ollama before the build, and note them in `progress.md`.

| Mode | Model | Where | Use |
|---|---|---|---|
| **Default (API)** | `gemma-4-31b-it` (31B dense) | Gemini API with AI Studio key | Best accuracy; main demo and headline numbers |
| **Fast (API)** | `gemma-4-26b-a4b-it` (26B MoE, ~4B active) | Gemini API | Lower latency; second benchmark point |
| **Local / offline** | Gemma 4 **E4B** (small) | Ollama (`ollama pull` the Gemma 4 E4B tag from ollama.com/library; check the exact tag) | Privacy demo; edge-size benchmark point |
| Optional smaller | Gemma 4 E2B | Ollama | Only if time allows |

**API keys:** open aistudio.google.com → API Keys → create key. **Every member creates their own key** so rate limits aren't shared. Keys live in `.env` (git-ignored); commit only `.env.example`.

```
DRIFT_BASE_URL=<Gemini API OpenAI-compatible base URL, from AI Studio docs>
DRIFT_API_KEY=...
DRIFT_MODEL=gemma-4-31b-it
DRIFT_FOLD_SYSTEM=false
# local mode
# DRIFT_BASE_URL=http://localhost:11434/v1
# DRIFT_MODEL=<gemma 4 E4B tag>
```

**License:** read the Gemma 4 model card and license text, and quote them accurately in the README (public sources currently disagree on the exact license wording, so verify).

## 10. App Flow

```
1. Invoke    → python scripts/drift.py scan <web-repo> [--diff main..HEAD] [--no-llm] [--no-images]
2. Detect    → confirm web project (package.json; Next / Express / Vite)
3. Discover  → source files, markdown docs, referenced local images
4. Extract   → facts (A) ∥ text claims (B) ∥ image claims (B → C vision → B)
5. Narrow    → (diff mode) only claims touching changed facts
6. Match     → per-kind deterministic rules → OK / STALE / SUSPECT
7. Judge     → SUSPECT → batched Gemma 4 calls → validated verdicts (cached)
8. Patch     → text findings: unified diff + git apply --check; image findings: replacement note
9. Report    → drift-report.json + drift-report.md + exit code
10. Agent    → reads JSON, applies patches or asks the user to approve
```

No `package.json` → exit with a clear "not a web project" message.

## 11. `SKILL.md` Requirements

```markdown
---
name: docs-drift-detector
description: Detects documentation drift in JavaScript/TypeScript web projects (Next.js, Express, Vite/React): stale npm scripts, env vars, API routes, ports, Node versions, dependencies, code samples and screenshots in README/docs, and proposes patches. Powered by Gemma 4 (Gemini API or local Ollama). Use after code changes or before releases.
---
# Instructions
1. Set DRIFT_* env vars (Gemini API key or local Ollama)
2. Run `python scripts/drift.py scan <repo> [--diff base..head]`
3. Read `drift-report.json`; review each STALE finding and its patch
4. Apply with `git apply` after user confirmation
```
Validate: folder name equals `name`, frontmatter valid, concise instructions, relative script paths. Re-read the Agent Skill spec at the start and re-validate in the last hour.

## 12. Testing Strategy

| Layer | What | Owner |
|---|---|---|
| Unit: pkg/env/routes/ports extractors | Next, Express, Vite snippets | A |
| Unit: doc parser, image finder, matcher | edge cases, allow-list, dynamic routes, fuzzy match, image size/count caps | B |
| Unit: LLM client, judge, vision, patcher | mocked text and image responses, malformed JSON, retry, system-role folding | C |
| Integration | full run per fixture (text only, then with images) | each member, one fixture |
| Benchmark | planted drift (text and image), per model size | A (31B), B (26B-A4B), C (E4B local) run; all verify |
| Real-repo test | one real public web repo each | A (Next.js), B (Express), C (Vite/React) |
| Skill compliance | spec validation plus a fresh-agent run | C builds; A, B cross-check |

**Cross-testing rule:** A→B's matcher and image finder, B→C's judge/vision/patcher, C→A's extractors.

## 13. Benchmark Design

Three web fixtures, each with ~10 planted text drifts, ~4 text decoys, and **2 screenshots** (one drifted, one current/decoy):

| Fixture | Owner | Planted text drift (examples) | Screenshots |
|---|---|---|---|
| `next_app` (App Router + Prisma) | A | renamed script, route to `/api/v2/…`, `NEXT_PUBLIC_` var renamed, Node 16→20, removed Prisma | terminal showing old script/port (drifted); `.env` example (current) |
| `express_api` | B | removed env var, changed port, GET→POST, router prefix, broken import | Swagger/Postman-style screenshot with old route (drifted); terminal (current) |
| `vite_react` | C | `VITE_` var renamed, script renamed, Tailwind v3→v4, missing component path | terminal with old script (drifted); UI screenshot (current) |

Screenshots can be made with a real terminal capture or generated with Pillow. Keep them clean and legible.

`expected.json` is ground truth; `run_bench.py --model <id>` prints precision, recall (text and image separately), calls saved, patch validity, runtime, and compares with a naive `grep` baseline. Results go into a **per-model-size table** in `progress.md` and the README:

| Model | Mode | Text recall | Image recall | False positives | Time |
|---|---|---|---|---|---|
| gemma-4-31b-it | API | | | | |
| gemma-4-26b-a4b-it | API | | | | |
| Gemma 4 E4B | local | | | | |

## 14. Stages
See `stages.md` for the hour-by-hour plan and per-member tasks.

## 15. Definition of Done

- [ ] Public repo, MIT license from the first commit
- [ ] `SKILL.md` valid under the Agent Skill spec
- [ ] Gemma 4 default documented with model card and license link
- [ ] API mode (31B) and local mode (E4B) both run; `--no-llm` runs
- [ ] P0 claim kinds working on all three fixtures
- [ ] Image claims working on at least two fixtures
- [ ] Benchmark table per model size in README
- [ ] Demo on a real web repo's older commit, including one screenshot finding
- [ ] README explains why Gemma 4 and maps to the track brief
- [ ] Every member has commits and reviewed PRs
- [ ] Fresh-clone install under 3 minutes
- [ ] Submission(s) added before the deadline

## 16. Contingency Plan

| If… | Then… |
|---|---|
| Vision reads are unreliable | Keep only high-confidence image claims; report others as "needs human"; demo with clean terminal screenshots |
| Gemini API OpenAI-compat lacks image input or JSON mode | Switch `llm.py` to the native Google SDK adapter |
| Rate-limited | Per-member keys; cache; 26B-A4B; local E4B; `--no-llm` for clear-cut claims |
| Express prefix resolution is hard | Same-file prefixes only; others SUSPECT |
| Behind at 4:00 | Cut diff mode, `.driftrc`, samples check, components; protect image claims and the model-size benchmark (the Gemma 4 differentiators) |
| Only one category allowed | Submit under the one that fits the judging criteria best; same repo |
