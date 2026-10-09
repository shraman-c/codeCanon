# PRD — docs-drift-detector (Web Dev Edition, Gemma 4)

**Tracks:**
1. MLH Hacktoberfest Hack Day — **Best Open-Source AI Project** (Agent Skill + open-weight AI)
2. MLH Hacktoberfest Hack Day — **Best Use of Gemma 4** (Google DeepMind): multimodal, focused AI tool, rapid prototyping through the Gemini API

> Confirm on the MLH page that one project may be submitted to both categories. If not, pick one and keep the other as a stretch.

**Type:** Agent Skill (Agent Skill Open Standard) powered by **Gemma 4** (open weights)
**Target repos:** web development projects only (Next.js, Express, Vite/React; JS/TS)
**Build window:** 6–7 hours, team of 3
**License:** MIT, public GitHub repo

---

## 1. Problem Statement

Web projects change fast and their docs don't. A dev renames an npm script, moves an API route to `/api/v2/...`, changes the dev server port, drops an env var, bumps the Node version, or redesigns a screen. The README, setup guide and API docs keep saying the old thing, **and so do their screenshots**: a terminal screenshot showing `npm run dev:local` on port 3000, a `.env` example image, a Swagger or dashboard screenshot. New contributors run a script that no longer exists, set the wrong env var, or `curl` an endpoint that returns 404. This is **documentation drift**, and in web repos it breaks onboarding on day one.

Existing solutions fall into two camps:

1. **Closed, paid products** (Swimm, Mintlify) that sync docs and code semantically but are proprietary, hosted and text-only.
2. **Open-source tools** that are mostly link checkers, markdown linters or docstring checkers. They check formatting, not whether `npm run dev:local` still exists, and none of them read screenshots.

**Goal:** an open-source Agent Skill, powered by **Gemma 4**, that scans a web-dev repo and finds documentation (**text and images**) that no longer matches the code or config, explains why, and proposes a ready-to-apply patch. Deterministic analysis handles everything checkable without a model. Gemma 4 handles ambiguous semantic cases and reads the screenshots in the docs.

**One-line pitch:** *"Your routes, scripts and env vars changed. Your README, and its screenshots, didn't. Gemma 4 catches it and fixes it, on your laptop or through the Gemini API."*

---

## 2. Why Gemma 4 (answer to the track brief)

| Track idea | How this project uses it |
|---|---|
| **Multimodal experience** | Gemma 4 reads README screenshots (terminal output, `.env` examples, API/Swagger pages, UI) and turns them into checkable claims |
| **Focused AI tool** | A single-purpose productivity tool for web developers and OSS maintainers |
| **Rapid prototyping with the Gemini API** | Developed against the Gemini API (AI Studio key) for speed; the same code runs fully local on Ollama with a small Gemma 4 for privacy |
| **Open weights** | Local mode means repo content never has to leave the machine; benchmark shows how small a Gemma 4 can be and still work |

---

## 3. Scope: Web Dev Repos Only

**Supported project types (v1)**
| Type | Detected by |
|---|---|
| Next.js (App Router and Pages Router) | `next` in dependencies, `app/` or `pages/` folder |
| Express APIs | `express` in dependencies, `app.get/post(...)`, `router.*` |
| Vite + React (or plain React) apps | `vite` / `react` in dependencies, `src/` |

**Languages:** JS/TS (`.js .jsx .ts .tsx .mjs`), `package.json`, `.env.example`, config files.
**Docs:** `README.md`, `docs/**/*.md`, `CONTRIBUTING.md`, `.env.example` comments, **images referenced from those docs** (png, jpg, webp).

**Out of scope:** Python/Go/Java backends, mobile apps, non-JS stacks, docs-site generators' internals, prose quality, link checking, video or audio.

---

## 4. What Counts as Drift (the Claims We Check)

| # | Doc claim | Source of truth | Example drift | Priority |
|---|---|---|---|---|
| 1 | `npm run <script>`, `pnpm/yarn/bun <script>` | `package.json` → `scripts` | README says `npm run dev:local`; renamed to `dev` | P0 |
| 2 | Env var names | `process.env.X`, `import.meta.env.VITE_X`, `.env.example` | Docs list `DB_URL`; code reads `DATABASE_URL` | P0 |
| 3 | API endpoints (`GET /api/users`, curl) | Next route files, Express routes | Route moved to `/api/v2/users` | P0 |
| 4 | Ports and URLs | `listen(...)`, `-p` in scripts, vite config | Server now on 4000 | P0 |
| 5 | Runtime versions ("Node 16+") | `engines`, `.nvmrc` | Engines now `>=20` | P0 |
| 6 | **Screenshot claims** (commands, ports, URLs, env names, endpoints visible in images) | Same facts as 1–5 | Terminal screenshot shows old script name or port | **P1 (Gemma 4 vision)** |
| 7 | Dependencies/libraries mentioned | `package.json` | Prisma removed; Tailwind v3 → v4 | P1 |
| 8 | Code samples (imports, file paths) | File system, dependencies | `./lib/db` no longer exists | P1 |
| 9 | Component usage and props | Exported component prop types | `variant` renamed to `intent` | P2 |
| 10 | Config references | Config files | Alias `@/lib` changed | P2 |

Screenshot findings cannot be patched as text: the report says which image is outdated, quotes what the model read from it, shows the conflicting fact, and suggests replacing the image. If the image's caption or surrounding text is wrong, that text is patched as usual.

---

## 5. Target Users

| User | Pain |
|---|---|
| OSS web maintainers | PRs change behaviour; nobody updates docs or screenshots |
| New contributors | Follow README, setup fails |
| AI coding agents | Need a callable skill to verify docs after editing code |
| Privacy-conscious teams | Want docs checks without sending code to a third party (local Gemma 4) |

---

## 6. Goals and Non-Goals

### Goals (must ship in 6–7 h)
- G1. Extract **facts** from web repos: npm scripts, env vars, routes, ports, engines (P1: dependencies).
- G2. Extract **claims** from Markdown docs for the same categories.
- G3. Deterministic matching for high-confidence drift.
- G4. **Gemma 4** judgement for ambiguous claims.
- G5. Structured JSON findings plus unified-diff patches.
- G6. Two modes: full-repo scan and `--diff <base>..<head>`.
- G7. Package as a valid Agent Skill (`SKILL.md` plus scripts).
- G8. **Gemma 4 as the default model** via the Gemini API (AI Studio key) with a **local Ollama** mode; endpoint configurable.
- G9. **Screenshot claims:** Gemma 4 vision reads images in the docs and feeds the same matcher (P1, but the key differentiator for the Gemma 4 track).
- G10. Benchmark on planted-drift fixtures **across Gemma 4 sizes** (31B, 26B-A4B, local E4B).

### Non-Goals
- Training or fine-tuning, auto-committing changes, non-web stacks, prose or grammar checks, editing image files.

---

## 7. Functional Requirements

| ID | Requirement | Priority |
|---|---|---|
| FR1 | Parse `package.json`: scripts, dependencies, devDependencies, engines | P0 |
| FR2 | Extract env vars from `process.env.X`, `process.env["X"]`, `import.meta.env.X`, and `.env.example` | P0 |
| FR3 | Extract routes: Next `app/**/route.ts`, `pages/api/**`, Express `app\|router.get/post/...` | P0 |
| FR4 | Extract ports from `listen(N)`, `-p N` / `--port N` in scripts, vite config | P0 |
| FR5 | Parse Markdown: inline code, fenced blocks, headings, ±1 paragraph context | P0 |
| FR6 | Match claims to facts; classify `OK`, `STALE`, `SUSPECT` | P0 |
| FR7 | Gemma 4 verdict on `SUSPECT` claims only; JSON output validated | P0 |
| FR8 | Unified-diff patch generation, verified with `git apply --check` | P0 |
| FR9 | **Find local images in docs; send each to Gemma 4 vision; extract commands, URLs/ports, env names, endpoints, versions as claims (marked `source: image`)** | P1 |
| FR10 | **Image findings reported with image path, extracted text, conflicting fact; no text patch unless caption is wrong** | P1 |
| FR11 | `--diff` mode using `git diff` | P1 |
| FR12 | Dependency and code-sample checks (imports resolve, packages exist, `node --check`) | P1 |
| FR13 | Markdown report in addition to JSON; CI exit code | P1 |
| FR14 | `--no-llm` deterministic-only mode (skips images too) | P1 |
| FR15 | Model switch by env vars: Gemini API (31B / 26B-A4B) or local Ollama (E4B) | P0 |
| FR16 | React component props extraction and usage check | P2 |
| FR17 | `.driftrc.json` (ignore paths, model, threshold, image limits) | P2 |

---

## 8. Non-Functional Requirements

- **Open-weight:** default is Gemma 4; license and model card linked in the README.
- **Privacy:** only short snippets and referenced images are sent to the API; local mode sends nothing out.
- **Speed:** < 60 s on a ~100-file repo with ≤ 10 docs and ≤ 10 images (text path); image reading adds a few seconds per image.
- **Cost and limits:** deterministic pre-filter plus cache keep calls low; image count capped (default 10) and image size capped (default 1.5 MB) before sending.
- **Reliability:** malformed model output never crashes the run (schema validation plus one retry). Unsupported system role handled by folding the system prompt into the user message.
- **Reproducibility:** `temperature=0`; prompts versioned in `references/prompts.md`.

---

## 9. Success Metrics

| Metric | Target |
|---|---|
| Recall on planted text drift (~30 across 3 fixtures) | ≥ 80 % (31B) |
| Recall on planted **screenshot** drift (~6 across 3 fixtures) | ≥ 60 % |
| False-positive rate (decoys flagged) | ≤ 15 % |
| LLM calls saved by deterministic pre-filter | ≥ 60 % |
| Patches that apply cleanly | ≥ 90 % |
| Local E4B recall as % of 31B recall | reported |
| Install to first report | < 3 minutes |
| Naive `grep` baseline recall | reported for comparison |

---

## 10. User Stories

1. *As a maintainer*, I run the skill on a PR diff and see which README lines, and screenshots, the PR made wrong.
2. *As a contributor*, I scan a repo and get a prioritised list of broken setup instructions.
3. *As an AI agent*, I call the skill after changing routes or scripts and get JSON to patch the docs myself.
4. *As a privacy-conscious team*, I point it at local Gemma 4 so nothing leaves my machine.

---

## 11. Deliverables

- Public GitHub repo with MIT `LICENSE` from the first commit
- Valid `SKILL.md`
- Python CLI and library (`drift/`) that analyses JS/TS web repos
- Three web fixtures (Next.js, Express, Vite+React) with planted text drift, planted screenshot drift and decoys
- README: install, usage, **why Gemma 4**, model setup (Gemini API and Ollama), benchmark table per model size, limitations, demo GIF
- `progress.md` kept current

---

## 12. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Gemma 4 hallucinates drift | Deterministic pre-filter, confidence threshold, require quoted evidence from facts |
| Vision misreads screenshots | Treat image claims as SUSPECT-first; require the extracted text to be quoted; lower confidence; decoy screenshots in benchmark |
| Free-tier rate limits on the Gemini API | Content-hash cache; each member uses their own AI Studio key; switch to 26B-A4B or local E4B |
| Gemma API quirks (system role, JSON mode) | Test in Stage 0; `fold_system_prompt` flag; JSON repair retry |
| Framework patterns missed | Scope to Next, Express, Vite; document limits; normalise dynamic segments |
| Spec compliance of `SKILL.md` | Validate at hour 1 and in the last hour |
| Entering two categories not allowed | Check rules in Stage 0; the project works for either |
| Scope creep | P1/P2 cut first; P0 frozen at end of Stage 2 |

---

## 13. Post-Hackathon Ideas

GitHub Action, auto-PR bot, regenerate screenshots automatically with Playwright, Fastify/NestJS/Remix/SvelteKit support, OpenAPI-vs-docs checks, Docusaurus/MDX.
