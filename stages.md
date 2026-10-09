# stages.md — docs-drift-detector (Web Dev Edition, 7 hours, 3 members)

**A = Code/facts side · B = Docs side · C = AI side**
Everyone works on short-lived branches and opens PRs against `main`. Each PR gets one review from a teammate, which doubles as cross-testing. Track every task in `progress.md`.

| Stage | Window | Goal |
|---|---|---|
| 0 | 0:00–0:30 | Kickoff: repo, schema, keys |
| 1 | 0:30–2:30 | Core modules built in parallel (scripts, env, docs parsing, LLM client) |
| 2 | 2:30–4:00 | Routes, ports, matcher, judge, patcher; end-to-end on one fixture |
| 3 | 4:00–5:00 | CLI, report, skill packaging |
| 4 | 5:00–6:15 | Parallel testing on 3 fixtures and 3 real web repos; benchmark |
| 5 | 6:15–7:00 | Polish, demo, submit |

---

## Stage 0 — Kickoff (0:00–0:30)

| Member | Tasks |
|---|---|
| A | Create the public repo with `LICENSE` in the first commit, skeleton folders, `.gitignore`, collaborators. Pick the web fixture stack and list target web repos for Stage 4. Push. |
| B | Write `models.py` with the web fact/claim kinds and agree `references/schema.json` with A and C. |
| C | Create API keys on 2 providers, commit `.env.example`, run a hello-world call to the chosen open-weight model, read the Agent Skill spec. |

**Exit:** repo public, schema agreed, all three can clone, branch, push and call the model.

## Stage 1 — Core build, parallel (0:30–2:30)

| Member | Tasks |
|---|---|
| A | `detect.py`, `extract_pkg.py` (scripts, deps, engines, `.nvmrc`), `extract_env.py` (`process.env`, `import.meta.env`, `.env.example`). Unit tests with Next/Express/Vite snippets. |
| B | `extract_docs.py`: npm-run commands, env vars, `GET /path` and curl, localhost ports, Node versions, fenced samples, context. Unit tests. |
| C | `llm.py`: OpenAI-compatible client, retry, content-hash cache, JSON validation. `prompts.md` v1 with web hints. Mocked tests. |

**Exit:** each module works alone with passing tests; PRs merged and reviewed.

## Stage 2 — Routes, matching, judging (2:30–4:00)

| Member | Tasks |
|---|---|
| A | `extract_routes.py` (Next App and Pages routers, Express routes and simple prefixes), `extract_ports.py`. If time: `gitdiff.py`. |
| B | `match.py`: per-kind rules (scripts, env, routes with dynamic-segment normalisation, ports, engines), allow-list, `OK/STALE/SUSPECT`. Tests. |
| C | `judge.py`: batched verdicts, schema check, threshold. `patch.py`: unified diff, deterministic suggestions, `git apply --check`. |

**Exit:** the full pipeline runs on one fixture with `--no-llm` and with the LLM.
**Scope freeze:** P0 only from here (scripts, env, routes, ports, engines). Cut P1/P2 if behind.

## Stage 3 — Integration and packaging (4:00–5:00)

| Member | Tasks |
|---|---|
| A | `scripts/drift.py` CLI wiring (`scan`, `--diff`, `--no-llm`, `--config`). `gitdiff.py` if not done. `extract_components.py` only if ahead. |
| B | `report.py` (JSON and Markdown, exit codes). `samples.py` (relative imports, deps, `node --check`) as P1. `.driftrc` if time. |
| C | `SKILL.md` finalised and validated against the spec. Test with a real agent invoking the skill on a web repo. |

**Exit:** one command produces a report and patches; the skill loads in an agent. Each person reviews a teammate's PR.

## Stage 4 — Parallel testing and benchmark (5:00–6:15)

Testing is split across all three. Nobody only tests their own work.

| Member | Fixture (planted drift and decoys) | Real-repo run | Break-test target |
|---|---|---|---|
| A | `next_app` (App Router + Prisma) | A real public Next.js repo | B's matcher (dynamic routes, `NEXT_PUBLIC_` prefixes, fuzzy names) |
| B | `express_api` | A real public Express repo | C's judge and patcher (malformed JSON, empty docs, long READMEs) |
| C | `vite_react` | A real public Vite/React repo | A's extractors (route groups, nested routers, dynamic env access) |

**Last 15 minutes, together:** A runs `run_bench.py`, B and C verify the numbers, then the team triages and fixes the top bugs in parallel. Record results in `progress.md`.

## Stage 5 — Polish and submit (6:15–7:00)

| Member | Tasks |
|---|---|
| A | Demo scenario on a real web repo's older commit (e.g. diff where a route or script was renamed). Record GIF or video. |
| B | README: install, usage, model setup, supported web stacks, benchmark table, limitations. Lint pass, check no secrets in history. |
| C | Final `SKILL.md` re-validation. Ollama local-mode check. Tag `v0.1.0`. |
| All | Fresh-clone install test on a teammate's machine. Submit via "Add Submission". Update `progress.md`. |

---

## Contingency Rules

| If… | Then… |
|---|---|
| Express routers get messy | Same-file prefixes only; others become SUSPECT |
| Components/props slip | Cut (P1); ship scripts, env, routes, ports, engines |
| Rate-limited | Switch provider via env vars; use the cache; `--no-llm` for clear-cut claims |
| Patches don't apply cleanly | Emit `corrected_text` with a manual-review flag |
| Behind at 4:00 | Cut diff mode, `.driftrc`, Markdown report, samples check |
