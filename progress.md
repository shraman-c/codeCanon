# Progress & Plan — docs-drift-detector (`codeCanon`)

> Single source of truth for the team. Update after every merged PR or every 30 minutes, whichever is sooner.
> Status keys: ⬜ not started · 🟦 in progress · ✅ done · 🟥 blocked

**Team:** A = Code/facts side · B = Docs side · C = AI side (Gemma 4)
Fill in names: A: _Spandan_ B: _Spandan_ C: _Sourav_
**Start time:** 2026-10-09T00:00:00Z **Deadline:** ____ **Repo URL:** https://github.com/shraman-c/codeCanon
**Categories entering:** ☐ Best Open-Source AI Project ☑ Best Use of Gemma 4 (MLH allows both? **Yes — see decision log, but treat as pending host confirmation**)
**Default model (exact ID):** gemma-4-31b-it · **Fast:** gemma-4-26b-a4b-it · **Local:** Gemma 4 E4B (Ollama tag: `gemma4:e4b`)
**Base URL used:** `https://generativelanguage.googleapis.com/v1beta/openai/` (Gemini API OpenAI-compatible) **System role supported?** ☐ verified ☐ not verified (folding off for now, recheck in Stage 0 smoke tests with API key)
**Target stacks:** Next.js · Express · Vite/React (JS/TS web repos only)

---

## Dashboard

| Stage | Window | Status | Done / Total |
|---|---|---|---|
| 0 Kickoff | 0:00–0:30 | 🟦 | 5/8 |
| 1 Core build | 0:30–2:30 | ⬜ | 0/9 |
| 2 Routes, matching, judging | 2:30–4:00 | ⬜ | 0/7 |
| 3 Integration, image claims, packaging | 4:00–5:00 | ⬜ | 0/8 |
| 4 Parallel testing + benchmark | 5:00–6:15 | ⬜ | 0/11 |
| 5 Polish and submit | 6:15–7:00 | ⬜ | 0/9 |

## Claim-Kind Coverage

| Kind | Priority | Extractor (A) | Doc parser (B) | Matcher (B) | Gemma judge/patch (C) | Works on fixtures |
|---|---|---|---|---|---|---|
| npm scripts | P0 | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| env vars | P0 | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| API routes | P0 | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| ports/URLs | P0 | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| Node/engines | P0 | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| **screenshot claims** | P1 (key) | n/a | ⬜ (`extract_images`) | ⬜ | ⬜ (`vision`) | ⬜ |
| dependencies | P1 | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| code samples | P1 | n/a | ⬜ | ⬜ | ⬜ | ⬜ |
| component props | P2 | ⬜ | n/a | ⬜ | ⬜ | ⬜ |

---

## Stage 0 — Kickoff (0:00–0:30)

| # | Task | Owner | Status | Notes |
|---|---|---|---|---|
| 0.1 | Repo public, `LICENSE` in first commit, skeleton folders, `.gitignore`, collaborators added | A | ✅ | `LICENSE` added; skeleton dirs created; `.gitignore` covers `.env`, `.drift_cache/`, `__pycache__`, etc. |
| 0.2 | Real web repos shortlisted (1 Next.js, 1 Express, 1 Vite/React) | A | 🟦 | See **Real-Repo Shortlist** below |
| 0.3 | Checked MLH rules: can one project enter both categories? | A | ✅ | Yes per organizer docs; same project can appear for every selected challenge. |
| 0.4 | `models.py` (with image-claim fields) + `references/schema.json` agreed | B | ✅ | Fact/Claim/Finding written; Claim has `source`, `image_path`, `extracted_text`; schema draft committed |
| 0.5 | Everyone has their own AI Studio key; `.env.example` committed | A, B, C | ✅ | `.env.example` committed with verified base URL, model, and Ollama tag; keys stay local |
| 0.6 | Gemma 4 31B smoke tests: text, JSON output, system role, one image call | C | 🟦 | Scripts built in `scripts/smoke/` (`smoke_text.py`, `smoke_json.py`, `smoke_system.py`, `smoke_image.py`, `smoke_image_native.py`); verified error handling; requires local `.env` with key |
| 0.7 | Local Ollama Gemma 4 E4B pulled and answering (note exact tag) | C | 🟦 | Confirmed tag `gemma4:e4b` (`ollama pull gemma4:e4b`). Script `smoke_local.py` built and skips gracefully if Ollama is offline |
| 0.8 | Each member can clone, branch, push, open a PR; Agent Skill spec read | A, B, C | ✅ | Branching and PRs verified; Agent Skill spec summarized in `docs/skill-spec-notes.md` |

---

## Stage 0 results

- **Exact working model ID(s):** `gemma-4-31b-it` (Verified in Google Gemini API official changelog/pricing docs).
- **Base URL used:** `https://generativelanguage.googleapis.com/v1beta/openai/`
- **JSON mode:** Test script `scripts/smoke/smoke_json.py` tests `response_format={"type": "json_object"}` and raw prompt fallback.
- **System role:** Test script `scripts/smoke/smoke_system.py` tests standard system message vs folded user prompt. Recommends `DRIFT_FOLD_SYSTEM=false` if accepted, or `true` if folded.
- **Image input:** Test script `scripts/smoke/smoke_image.py` tests terminal screenshot via OpenAI compat endpoint; native fallback implemented in `scripts/smoke/smoke_image_native.py` using `generateContent` REST endpoint.
- **Exact Ollama E4B tag:** `gemma4:e4b` (Command: `ollama pull gemma4:e4b`). Tested via `scripts/smoke/smoke_local.py` (skips cleanly if Ollama daemon is not running).
- **Failures / current errors:** Without `DRIFT_API_KEY` set in local `.env`, Gemini API requests return `400 / 401 API key not valid` as expected. Ollama local test skipped when Ollama is not installed/running.

---

## Stage 1 — Core build (0:30–2:30)

| # | Task | Owner | Status | Notes |
|---|---|---|---|---|
| 1.1 | `detect.py` + `extract_pkg.py` (scripts, deps, engines, `.nvmrc`) | A | ⬜ | |
| 1.2 | `extract_env.py` (`process.env`, `import.meta.env`, `.env.example`) | A | ⬜ | |
| 1.3 | Unit tests for 1.1–1.2 | A | ⬜ | |
| 1.4 | `extract_docs.py`: npm-run, env vars, routes/curl, ports, Node versions | B | ⬜ | |
| 1.5 | Unit tests for 1.4 | B | ⬜ | |
| 1.6 | `llm.py`: Gemini API + Ollama client, text and image messages, retry, cache, JSON validation | C | ⬜ | |
| 1.7 | System-role folding flag wired from Stage 0 decision | C | ⬜ | |
| 1.8 | `references/prompts.md` v1 (judge) with web hints | C | ⬜ | |
| 1.9 | Mocked tests for 1.6 (text and image) | C | ⬜ | |

## Stage 2 — Routes, matching, judging (2:30–4:00)

| # | Task | Owner | Status | Notes |
|---|---|---|---|---|
| 2.1 | `extract_routes.py`: Next App Router + Pages Router | A | ⬜ | |
| 2.2 | `extract_routes.py`: Express routes and same-file prefixes | A | ⬜ | |
| 2.3 | `extract_ports.py` | A | ⬜ | |
| 2.4 | `match.py`: per-kind rules, dynamic-route normalisation, allow-list, image-confidence discount + tests | B | ⬜ | |
| 2.5 | `judge.py`: batched verdicts, schema check, threshold | C | ⬜ | |
| 2.6 | `patch.py`: unified diff, deterministic suggestions, `git apply --check` | C | ⬜ | |
| 2.7 | End-to-end text run on one fixture (`--no-llm` and Gemma 4) | A, B, C | ⬜ | **P0 frozen after this** |

## Stage 3 — Integration, image claims, packaging (4:00–5:00)

| # | Task | Owner | Status | Notes |
|---|---|---|---|---|
| 3.1 | `scripts/drift.py` CLI: `scan`, `--diff`, `--no-llm`, `--no-images`, `--config` | A | ⬜ | |
| 3.2 | `gitdiff.py` diff mode | A | ⬜ | P1 |
| 3.3 | `next_app` fixture started (text drifts + 2 screenshots) | A | ⬜ | |
| 3.4 | `extract_images.py`: find local images, caps, hash cache, claims into matcher | B | ⬜ | P1 key |
| 3.5 | `report.py`: JSON + Markdown, image findings, model line, exit codes | B | ⬜ | |
| 3.6 | `vision.py`: prompt, JSON validation, empty/low-quality handling | C | ⬜ | P1 key |
| 3.7 | `SKILL.md` finalised, validated, invoked by a real agent on a web repo | C | ⬜ | |
| 3.8 | Cross-review: each PR reviewed by a different member | A, B, C | ⬜ | |

## Stage 4 — Parallel testing and benchmark (5:00–6:15)

| # | Task | Owner | Status | Notes |
|---|---|---|---|---|
| 4.1 | `next_app` fixture complete: ~10 text drifts + ~4 decoys + 2 screenshots | A | ⬜ | |
| 4.2 | `express_api` fixture complete: ~10 text drifts + ~4 decoys + 2 screenshots | B | ⬜ | |
| 4.3 | `vite_react` fixture complete: ~10 text drifts + ~4 decoys + 2 screenshots | C | ⬜ | |
| 4.4 | Real Next.js repo run + bug notes | A | ⬜ | Repo: `<Next.js shortlist pick>` |
| 4.5 | Real Express repo run + bug notes | B | ⬜ | Repo: `<Express shortlist pick>` |
| 4.6 | Real Vite/React repo run + bug notes | C | ⬜ | Repo: `<Vite/React shortlist pick>` |
| 4.7 | Benchmark with `gemma-4-31b-it` (API) | A | ⬜ | |
| 4.8 | Benchmark with `gemma-4-26b-a4b-it` (API) | B | ⬜ | |
| 4.9 | Benchmark with Gemma 4 E4B (local) | C | ⬜ | |
| 4.10 | Break-tests: A→B's matcher/image finder · B→C's judge/vision/patcher · C→A's extractors | A, B, C | ⬜ | |
| 4.11 | Merge results into the table below; top bugs triaged and fixed | A, B, C | ⬜ | |

## Stage 5 — Polish and submit (6:15–7:00)

| # | Task | Owner | Status | Notes |
|---|---|---|---|---|
| 5.1 | Demo scenario on a real web repo's old commit incl. an outdated screenshot | A | ⬜ | |
| 5.2 | Demo GIF / video recorded | A | ⬜ | |
| 5.3 | README: install, usage, Why Gemma 4, model setup, stacks, benchmark per size, limits | B | ⬜ | |
| 5.4 | Lint/format pass; no secrets in history | B | ⬜ | |
| 5.5 | Final `SKILL.md` re-validation | C | ⬜ | |
| 5.6 | Gemma 4 license wording and model card link verified in README | C | ⬜ | |
| 5.7 | Local-mode check on a clean machine | C | ⬜ | |
| 5.8 | Fresh-clone install test on a teammate's machine | A, B, C | ⬜ | |
| 5.9 | Tag `v0.1.0`; submit via "Add Submission" in each eligible category | All | ⬜ | |

---

## Real-Repo Shortlist (Stage 0 pick; refine before Stage 4)

Pick small, well-documented public repos with a real README and `package.json`.

| Stack | Pick | Why this one this round |
|---|---|---|
| Next.js | `https://github.com/vercel/next.js` (too large — use a small example sub-repo or a well-documented Next.js starter instead) | Placeholder; narrow to a small Next.js example for the real-repo run |
| Express | `https://github.com/gothinkster/node-express-realworld-example-app` | Small, documented Express + Prisma-style API example |
| Vite/React | `https://github.com/amannn/vite-react-starter` | Minimal Vite + React starter; good for real-repo smoke test if reachable |

Note: the shortlist above is provisional until Stage 4 picks are rechecked for reachability and docs quality. The repo list still needs one concrete small Next.js repo; do not treat the large monorepo as the real-repo target.

## Benchmark Results (fill in at Stage 4)

**Per model size**

| Model | Mode | Text recall | Image recall | False-positive rate | LLM calls saved | Time (100-file repo) |
|---|---|---|---|---|---|---|
| gemma-4-31b-it | API | | | | | |
| gemma-4-26b-a4b-it | API | | | | | |
| Gemma 4 E4B | local | | | | | |
| Naive grep baseline | n/a | | n/a | | n/a | |

Targets: text recall ≥ 80 % (31B), image recall ≥ 60 %, false positives ≤ 15 %, calls saved ≥ 60 %, patches applying cleanly ≥ 90 %.

**Per fixture (31B)**

| Fixture | Planted text | Caught | Planted image | Caught | Decoys flagged | Notes |
|---|---|---|---|---|---|---|
| next_app | | | | | | |
| express_api | | | | | | |
| vite_react | | | | | | |

## Contribution Log (one line per merged PR)

| Time | PR / commit | Author | Reviewer | Summary |
|---|---|---|---|---|
| 2026-10-09 | initial Stage 0 verification commit (LICENSE, models, schema, .env.example, progress update) | A/B/C | — | Stage 0 scaffolding started |
| 2026-10-09 | Stage 0 AI layer setup with smoke tests | C | A | Added smoke tests, verified model IDs and base URL, spec notes |

## Decisions Log

| Time | Decision | Why | Who |
|---|---|---|---|
| 2026-10-09 | Scope = JS/TS web repos only (Next, Express, Vite/React) | track brief + TRD | all |
| 2026-10-09 | Default model = Gemma 4 (31B via Gemini API) | track fit, open weights, multimodal | all |
| 2026-10-09 | Entering categories: Best Open-Source AI Project + Best Use of Gemma 4 (both eligible per MLH organizer docs, pending host confirmation) | organizer guidance says same project can be submitted to every selected challenge | A |
| 2026-10-09 | `.env.example` committed; real keys stay local and git-ignored | keep keys out of history | all |
| 2026-10-09 | Exact Gemini base URL verified as `https://generativelanguage.googleapis.com/v1beta/openai/`, model `gemma-4-31b-it`, Ollama tag `gemma4:e4b` | Stage 0 official doc verification | C |

## Blockers

| Time | Blocker | Owner | Resolution |
|---|---|---|---|
| 2026-10-09 | AI Studio key not created in this workspace; Gemma 4 smoke tests not run here | C | create key locally and retry smoke tests before Stage 1; record model IDs/tags once confirmed |

## Bugs Found in Testing

| ID | Found by | Module (owner) | Description | Status |
|---|---|---|---|---|
| | | | | |

## Submission Checklist

- [ ] Repo public, `LICENSE` present
- [ ] `SKILL.md` valid under Agent Skill Open Standard
- [ ] Gemma 4 named as the core model; model card and license linked in README
- [ ] README explains Why Gemma 4 (multimodal, focused tool, rapid prototyping, open weights)
- [ ] Demo video/GIF includes a screenshot finding
- [ ] Benchmark table per model size in README
- [ ] No API keys in git history
- [ ] All 3 members have commits and reviewed PRs
- [ ] Submission added in each eligible category before the deadline
