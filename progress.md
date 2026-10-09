# progress.md — docs-drift-detector (Web Dev Edition, Gemma 4)

> Single source of truth for the team. Update after every merged PR or every 30 minutes, whichever is sooner.
> Status keys: ⬜ not started · 🟦 in progress · ✅ done · 🟥 blocked

**Team:** A = Code/facts side · B = Docs side · C = AI side (Gemma 4)
Fill in names: A: ________ B: ________ C: ________
**Start time:** ____ **Deadline:** ____ **Repo URL:** ____
**Categories entering:** ☐ Best Open-Source AI Project ☐ Best Use of Gemma 4 (MLH allows both? ____)
**Default model (exact ID):** gemma-4-31b-it · **Fast:** gemma-4-26b-a4b-it · **Local:** Gemma 4 E4B (Ollama tag: ____)
**Base URL used:** ____ **System role supported?** ☐ yes ☐ no (folding on)
**Target stacks:** Next.js · Express · Vite/React (JS/TS web repos only)

---

## Dashboard

| Stage | Window | Status | Done / Total |
|---|---|---|---|
| 0 Kickoff | 0:00–0:30 | ⬜ | 0/8 |
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
| 0.1 | Repo public, `LICENSE` in first commit, skeleton folders, collaborators added | A | ⬜ | |
| 0.2 | Real web repos shortlisted (1 Next.js, 1 Express, 1 Vite/React) | A | ⬜ | |
| 0.3 | Checked MLH rules: can one project enter both categories? | A | ⬜ | |
| 0.4 | `models.py` (with image-claim fields) + `references/schema.json` agreed | B | ⬜ | |
| 0.5 | Everyone has their own AI Studio key; `.env.example` committed | A, B, C | ⬜ | |
| 0.6 | Gemma 4 31B smoke tests: text, JSON output, system role, one image call | C | ⬜ | |
| 0.7 | Local Ollama Gemma 4 E4B pulled and answering (note exact tag) | C | ⬜ | |
| 0.8 | Each member can clone, branch, push, open a PR; Agent Skill spec read | A, B, C | ⬜ | |

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
| 4.4 | Real Next.js repo run + bug notes | A | ⬜ | Repo: |
| 4.5 | Real Express repo run + bug notes | B | ⬜ | Repo: |
| 4.6 | Real Vite/React repo run + bug notes | C | ⬜ | Repo: |
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
| | | | | |

## Decisions Log

| Time | Decision | Why | Who |
|---|---|---|---|
| | Scope = JS/TS web repos only (Next, Express, Vite/React) | | |
| | Default model = Gemma 4 (31B via Gemini API) | Track fit, open weights, multimodal | |
| | Entering categories: ____ | | |

## Blockers

| Time | Blocker | Owner | Resolution |
|---|---|---|---|
| | | | |

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
