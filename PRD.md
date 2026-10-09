# PRD — docs-drift-detector (Web Dev Edition)

**Track:** MLH Hacktoberfest Hack Day — Best Open-Source AI Project
**Type:** Agent Skill (Agent Skill Open Standard) + open-weight LLM
**Target repos:** web development projects only (Next.js, Express, Vite/React; JS/TS)
**Build window:** 6–7 hours, team of 3
**License:** MIT, public GitHub repo

---

## 1. Problem Statement

Web projects change fast and their docs don't. A dev renames an npm script, moves an API route to `/api/v2/...`, changes the dev server port, drops an env var, bumps the Node version, or changes a component's props. The README, setup guide and API docs keep saying the old thing. New contributors run `npm run dev:local`, hit "missing script", set `DATABASE_URL` when the app now wants `POSTGRES_URL`, or `curl` an endpoint that returns 404. This is **documentation drift**, and in web repos it breaks onboarding on day one.

Existing solutions fall into two camps:

1. **Closed, paid products** (Swimm, Mintlify) that sync docs and code semantically but are proprietary and hosted.
2. **Open-source tools** that are mostly link checkers, markdown linters or docstring checkers. They check formatting, not whether `npm run dev:local` still exists.

**Goal:** an open-source Agent Skill that scans a web-dev repo, finds documentation statements that no longer match the code or config, explains why, and proposes a ready-to-apply patch. Deterministic analysis handles everything checkable without a model. An open-weight LLM handles the ambiguous semantic cases.

**One-line pitch:** *"Your routes, scripts and env vars changed. Your README didn't. We catch it and fix it."*

---

## 2. Scope: Web Dev Repos Only

**Supported project types (v1)**
| Type | Detected by |
|---|---|
| Next.js (App Router and Pages Router) | `next` in dependencies, `app/` or `pages/` folder |
| Express APIs | `express` in dependencies, `app.get/post(...)`, `router.*` |
| Vite + React (or plain React) apps | `vite` / `react` in dependencies, `src/` components |

**Languages:** JavaScript and TypeScript (`.js .jsx .ts .tsx .mjs`), plus `package.json`, `.env.example`, config files.
**Docs:** `README.md`, `docs/**/*.md`, `CONTRIBUTING.md`, `.env.example` comments.

**Out of scope:** Python/Go/Java backends, mobile apps, non-JS stacks, docs-site generators' internals, prose quality, link checking.

---

## 3. What Counts as Drift (the Claims We Check)

| # | Doc claim | Code/config source of truth | Example drift |
|---|---|---|---|
| 1 | `npm run <script>`, `pnpm/yarn/bun <script>` | `package.json` → `scripts` | README says `npm run dev:local`; script was renamed to `dev` |
| 2 | Env var names (`DATABASE_URL`, `NEXT_PUBLIC_API_URL`) | `process.env.X`, `import.meta.env.VITE_X`, `.env.example` | Docs list `DB_URL`; code reads `DATABASE_URL` |
| 3 | API endpoints (`GET /api/users`, curl examples) | Next route files, Express `app.get(...)` / routers | Route moved to `/api/v2/users` |
| 4 | Ports and URLs (`localhost:3000`) | `listen(...)`, `-p` flag in scripts, vite config | Server now on 4000 |
| 5 | Runtime/tool versions ("Node 16+") | `package.json` → `engines`, `.nvmrc` | Engines now `>=20` |
| 6 | Dependencies/libraries mentioned ("uses Prisma", "Tailwind v3") | `package.json` dependencies | Prisma removed; Tailwind now v4 |
| 7 | Component usage and props (`<Button variant="primary">`) | Exported component prop types | Prop `variant` renamed to `intent` |
| 8 | Code samples (imports, file paths) | File system, dependency list | `import x from './lib/db'` file no longer exists |
| 9 | Config references (`next.config.js` option, `tsconfig` path alias) | Config files | Alias `@/lib` changed |

P0 = claims 1–5. P1 = claims 6–8. P2 = claim 9.

---

## 4. Target Users

| User | Pain |
|---|---|
| OSS web maintainers | PRs change behaviour; nobody updates docs |
| New contributors | Follow README, setup fails |
| AI coding agents | Need a callable skill to verify docs after editing code |
| Small teams | Can't afford Swimm/Mintlify |

---

## 5. Goals and Non-Goals

### Goals (must ship in 6–7 h)
- G1. Extract **facts** from web repos: npm scripts, env vars, routes, ports, engines, dependencies (P1: component props).
- G2. Extract **claims** from Markdown docs for the same categories.
- G3. Deterministic matching for high-confidence drift (claim references something that no longer exists).
- G4. LLM judgement (open-weight) for ambiguous claims.
- G5. Output structured JSON findings plus unified-diff patches.
- G6. Two modes: full-repo scan and `--diff <base>..<head>` (only claims touching changed facts).
- G7. Package as a valid Agent Skill (`SKILL.md` plus scripts).
- G8. Configurable model endpoint (any OpenAI-compatible API, hosted or local Ollama).
- G9. Benchmark on planted-drift web fixtures with precision and recall.

### Non-Goals
- Training a model, auto-committing changes, non-web stacks, prose or grammar checks.

---

## 6. Functional Requirements

| ID | Requirement | Priority |
|---|---|---|
| FR1 | Parse `package.json`: scripts, dependencies, devDependencies, engines | P0 |
| FR2 | Extract env vars from `process.env.X`, `process.env["X"]`, `import.meta.env.X`, and `.env.example` | P0 |
| FR3 | Extract routes: Next.js `app/**/route.ts` (exported GET/POST/…), `pages/api/**`, Express `app|router.get/post/put/delete/patch('/path')` | P0 |
| FR4 | Extract ports from `listen(N)`, `-p N` / `--port N` in scripts, `server.port` in vite config | P0 |
| FR5 | Parse Markdown: inline code, fenced `bash/sh/js/ts/json` blocks, headings, ±1 paragraph context | P0 |
| FR6 | Match claims to facts; classify `OK`, `STALE`, `SUSPECT` | P0 |
| FR7 | LLM verdict on `SUSPECT` claims only; JSON output validated | P0 |
| FR8 | Unified-diff patch generation, verified with `git apply --check` | P0 |
| FR9 | `--diff` mode using `git diff` to find changed facts | P1 |
| FR10 | Exported React component props extraction and usage check | P1 |
| FR11 | Code sample checks: relative imports resolve, imported packages exist in dependencies, `node --check` on JS blocks | P1 |
| FR12 | Markdown report in addition to JSON; CI exit code | P1 |
| FR13 | `--no-llm` deterministic-only mode | P1 |
| FR14 | `.driftrc.json` (ignore paths, model, threshold) | P2 |

---

## 7. Non-Functional Requirements

- **Open-weight requirement:** default model is open-weight and documented in the README.
- **Privacy:** only short snippets are sent to the model; local Ollama mode sends nothing out.
- **Speed:** < 60 s on a repo with ~100 source files and ~10 docs.
- **Cost:** deterministic pre-filter keeps LLM calls under ~50 per scan.
- **Reliability:** malformed LLM output never crashes the run (schema validation plus one retry).
- **Reproducibility:** `temperature=0`; prompts versioned in `references/prompts.md`.

---

## 8. Success Metrics

| Metric | Target |
|---|---|
| Recall on planted drift (~30 issues across 3 web fixtures) | ≥ 80 % |
| False-positive rate (decoys flagged) | ≤ 15 % |
| LLM calls saved by deterministic pre-filter | ≥ 60 % |
| Patches that apply cleanly | ≥ 90 % |
| Install to first report | < 3 minutes |
| Naive `grep` baseline recall | reported for comparison |

---

## 9. User Stories

1. *As a maintainer*, I run the skill on a PR diff and see which README lines the PR made wrong.
2. *As a contributor*, I scan a repo and get a prioritised list of broken setup instructions.
3. *As an AI agent*, I call the skill after changing routes or scripts and get JSON to patch the docs myself.
4. *As a privacy-conscious team*, I point it at local Ollama so nothing leaves my machine.

---

## 10. Deliverables

- Public GitHub repo with MIT `LICENSE` from the first commit
- Valid `SKILL.md`
- Python CLI and library (`drift/`) that analyses JS/TS web repos
- Three web fixtures (Next.js, Express, Vite+React) with planted drift and decoys
- README with install, usage, model setup, benchmark table, limitations, demo GIF
- `progress.md` kept current

---

## 11. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| LLM hallucinates drift | Deterministic pre-filter, confidence threshold, require quoted evidence from code |
| Rate limits on free tiers | Content-hash cache, second provider, local Ollama |
| Framework patterns missed (dynamic routes, custom wrappers) | Scope to Next, Express, Vite; document limits; fuzzy route matching (`/users/:id` ≈ `[id]`) |
| Regex extraction misses edge cases | Cross-test with real repos in Stage 4 |
| Spec compliance of `SKILL.md` | Validate at hour 1 and in the last hour |
| Scope creep | P2 and P1 cut first; P0 frozen at end of Stage 2 |

---

## 12. Post-Hackathon Ideas

GitHub Action wrapper, auto-PR bot, Fastify/NestJS/Remix/SvelteKit support, OpenAPI-vs-docs checks, Docusaurus/MDX support.
