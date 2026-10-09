# progress.md — docs-drift-detector (Web Dev Edition)

> Single source of truth for the team. Update after every merged PR or every 30 minutes, whichever is sooner.
> Status keys: ⬜ not started · 🟦 in progress · ✅ done · 🟥 blocked

**Team:** A = Code/facts side · B = Docs side · C = AI side
Fill in names: A: ________ B: ________ C: ________
**Start time:** ____ **Deadline:** ____ **Repo URL:** ____
**Chosen model (exact ID):** ____ **Provider:** ____ **Fallback:** ____ **Local:** qwen2.5-coder:7b (Ollama)
**Target stacks:** Next.js · Express · Vite/React (JS/TS web repos only)

---

## Dashboard

| Stage | Window | Status | Done / Total |
|---|---|---|---|
| 0 Kickoff | 0:00–0:30 | ⬜ | 0/6 |
| 1 Core build | 0:30–2:30 | ⬜ | 0/8 |
| 2 Routes, matching, judging | 2:30–4:00 | ⬜ | 0/7 |
| 3 Integration and packaging | 4:00–5:00 | ⬜ | 0/7 |
| 4 Parallel testing + benchmark | 5:00–6:15 | ⬜ | 0/10 |
| 5 Polish and submit | 6:15–7:00 | ⬜ | 0/8 |

## Claim-Kind Coverage (update as kinds start working end-to-end)

| Kind | Priority | Extractor (A) | Doc parser (B) | Matcher (B) | Judge/patch (C) | Works on fixtures |
|---|---|---|---|---|---|---|
| npm scripts | P0 | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| env vars | P0 | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| API routes | P0 | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| ports/URLs | P0 | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| Node/engines | P0 | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| dependencies | P1 | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| component props | P1 | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| code samples | P1 | n/a | ⬜ | ⬜ | ⬜ | ⬜ |

---

## Stage 0 — Kickoff (0:00–0:30)

| # | Task | Owner | Status | Notes |
|---|---|---|---|---|
| 0.1 | Repo created and public, `LICENSE` in first commit, skeleton folders, collaborators added | A | ⬜ | |
| 0.2 | Target real web repos shortlisted (1 Next.js, 1 Express, 1 Vite/React) | A | ⬜ | |
| 0.3 | `models.py` web fact/claim kinds + `references/schema.json` agreed | B | ⬜ | |
| 0.4 | API keys on 2 providers, `.env.example` committed | C | ⬜ | |
| 0.5 | Hello-world call to chosen open-weight model works; Agent Skill spec read | C | ⬜ | |
| 0.6 | Each member can clone, branch, push, open a PR | A, B, C | ⬜ | |

## Stage 1 — Core build (0:30–2:30)

| # | Task | Owner | Status | Notes |
|---|---|---|---|---|
| 1.1 | `detect.py` + `extract_pkg.py` (scripts, deps, engines, `.nvmrc`) | A | ⬜ | |
| 1.2 | `extract_env.py` (`process.env`, `import.meta.env`, `.env.example`) | A | ⬜ | |
| 1.3 | Unit tests for 1.1–1.2 with Next/Express/Vite snippets | A | ⬜ | |
| 1.4 | `extract_docs.py`: npm-run, env vars, routes/curl, ports, Node versions | B | ⬜ | |
| 1.5 | Unit tests for 1.4 | B | ⬜ | |
| 1.6 | `llm.py`: client, retry, cache, JSON validation | C | ⬜ | |
| 1.7 | `references/prompts.md` v1 with web hints | C | ⬜ | |
| 1.8 | Mocked tests for 1.6 | C | ⬜ | |

## Stage 2 — Routes, matching, judging (2:30–4:00)

| # | Task | Owner | Status | Notes |
|---|---|---|---|---|
| 2.1 | `extract_routes.py`: Next App Router + Pages Router | A | ⬜ | |
| 2.2 | `extract_routes.py`: Express routes and same-file prefixes | A | ⬜ | |
| 2.3 | `extract_ports.py` | A | ⬜ | |
| 2.4 | `match.py`: per-kind rules, dynamic-route normalisation, allow-list + tests | B | ⬜ | |
| 2.5 | `judge.py`: batched verdicts, schema check, threshold | C | ⬜ | |
| 2.6 | `patch.py`: unified diff, deterministic suggestions, `git apply --check` | C | ⬜ | |
| 2.7 | End-to-end run on one fixture (`--no-llm` and LLM) | A, B, C | ⬜ | **Scope freeze: P0 only after this** |

## Stage 3 — Integration and packaging (4:00–5:00)

| # | Task | Owner | Status | Notes |
|---|---|---|---|---|
| 3.1 | `scripts/drift.py` CLI: `scan`, `--diff`, `--no-llm`, `--config` | A | ⬜ | |
| 3.2 | `gitdiff.py` diff mode | A | ⬜ | P1 |
| 3.3 | `extract_components.py` | A | ⬜ | P1, only if ahead |
| 3.4 | `report.py`: JSON + Markdown, exit codes | B | ⬜ | |
| 3.5 | `samples.py`: imports, deps, `node --check` | B | ⬜ | P1 |
| 3.6 | `SKILL.md` finalised, validated, invoked by a real agent on a web repo | C | ⬜ | |
| 3.7 | Cross-review: each PR reviewed by a different member | A, B, C | ⬜ | |

## Stage 4 — Parallel testing and benchmark (5:00–6:15)

| # | Task | Owner | Status | Notes |
|---|---|---|---|---|
| 4.1 | `next_app` fixture: ~10 planted drifts + ~4 decoys | A | ⬜ | |
| 4.2 | `express_api` fixture: ~10 planted drifts + ~4 decoys | B | ⬜ | |
| 4.3 | `vite_react` fixture: ~10 planted drifts + ~4 decoys | C | ⬜ | |
| 4.4 | Real Next.js repo run + bug notes | A | ⬜ | Repo: |
| 4.5 | Real Express repo run + bug notes | B | ⬜ | Repo: |
| 4.6 | Real Vite/React repo run + bug notes | C | ⬜ | Repo: |
| 4.7 | Break-test: A tests B's matcher | A | ⬜ | |
| 4.8 | Break-test: B tests C's judge/patcher · C tests A's extractors | B, C | ⬜ | |
| 4.9 | `run_bench.py` executed; metrics recorded below | A (run), B, C (verify) | ⬜ | |
| 4.10 | Top bugs triaged and fixed | A, B, C | ⬜ | |

## Stage 5 — Polish and submit (6:15–7:00)

| # | Task | Owner | Status | Notes |
|---|---|---|---|---|
| 5.1 | Demo scenario on a real web repo's older commit | A | ⬜ | |
| 5.2 | Demo GIF / video recorded | A | ⬜ | |
| 5.3 | README: install, usage, model setup, supported stacks, benchmark, limits | B | ⬜ | |
| 5.4 | Lint/format pass; no secrets in history | B | ⬜ | |
| 5.5 | Final `SKILL.md` re-validation | C | ⬜ | |
| 5.6 | Ollama local-mode check | C | ⬜ | |
| 5.7 | Fresh-clone install test on a teammate's machine | A, B, C | ⬜ | |
| 5.8 | Tag `v0.1.0`, submit via "Add Submission" | All | ⬜ | |

---

## Benchmark Results (fill in at Stage 4)

| Metric | Target | Actual |
|---|---|---|
| Recall (planted drift, all fixtures) | ≥ 80 % | |
| False-positive rate (decoys) | ≤ 15 % | |
| LLM calls saved by pre-filter | ≥ 60 % | |
| Patches applying cleanly | ≥ 90 % | |
| Naive grep baseline recall | n/a | |
| Run time on ~100-file repo | < 60 s | |

Per fixture:

| Fixture | Planted | Caught | Decoys flagged | Notes |
|---|---|---|---|---|
| next_app | | | | |
| express_api | | | | |
| vite_react | | | | |

## Contribution Log (one line per merged PR)

| Time | PR / commit | Author | Reviewer | Summary |
|---|---|---|---|---|
| | | | | |

## Decisions Log

| Time | Decision | Why | Who |
|---|---|---|---|
| | Scope = JS/TS web repos only (Next, Express, Vite/React) | | |
| | Default model = ___ | | |

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
- [ ] Open-weight model named and linked in README
- [ ] Demo video/GIF in README
- [ ] Benchmark table in README
- [ ] No API keys in git history
- [ ] All 3 members have commits and reviewed PRs
- [ ] Submission added before deadline
