# stages.md — docs-drift-detector (Web Dev Edition, Gemma 4, 7 hours, 3 members)

**A = Code/facts side · B = Docs side · C = AI side (Gemma 4)**
Everyone works on short-lived branches and opens PRs against `main`. Each PR gets one review from a teammate, which doubles as cross-testing. Track every task in `progress.md`.

| Stage | Window | Goal |
|---|---|---|
| 0 | 0:00–0:30 | Kickoff: repo, schema, AI Studio keys, Gemma 4 smoke tests |
| 1 | 0:30–2:30 | Core modules in parallel (scripts, env, docs parsing, Gemma client) |
| 2 | 2:30–4:00 | Routes, ports, matcher, judge, patcher; end-to-end on one fixture |
| 3 | 4:00–5:00 | CLI, report, image claims (vision), skill packaging |
| 4 | 5:00–6:15 | Parallel testing: 3 fixtures, 3 real repos, benchmark per Gemma 4 size |
| 5 | 6:15–7:00 | Polish, demo, submit |

---

## Stage 0 — Kickoff (0:00–0:30)

| Member | Tasks |
|---|---|
| A | Create the public repo with `LICENSE` in the first commit, skeleton folders, `.gitignore`, collaborators. Shortlist 3 real public web repos (Next, Express, Vite/React) for Stage 4. **Check MLH rules for submitting to both categories** and note the answer in `progress.md`. Push. |
| B | Write `models.py` (including `Claim.source`, `image_path`, `extracted_text`) and agree `references/schema.json` with A and C. |
| C | **Everyone creates an AI Studio key; C leads the smoke tests:** Gemma 4 31B text call, JSON-output call, system-role behaviour (decide `fold_system_prompt`), one image call with a terminal screenshot, and local Ollama E4B pull and call. Commit `.env.example`. Read the Agent Skill spec. |

**Exit:** repo public, schema agreed, all three have working keys, Gemma 4 text, JSON and image calls verified, system-role behaviour decided.

## Stage 1 — Core build, parallel (0:30–2:30)

| Member | Tasks |
|---|---|
| A | `detect.py`, `extract_pkg.py` (scripts, deps, engines, `.nvmrc`), `extract_env.py`. Unit tests with Next/Express/Vite snippets. |
| B | `extract_docs.py`: npm-run, env vars, `GET /path` and curl, localhost ports, Node versions, fenced samples, context. Unit tests. |
| C | `llm.py`: OpenAI-compatible client for Gemini API and Ollama, **text and image messages**, retry, content-hash cache, JSON validation, system-role folding. `prompts.md` v1 (judge). Mocked tests. |

**Exit:** each module works alone with passing tests; PRs merged and reviewed.

## Stage 2 — Routes, matching, judging (2:30–4:00)

| Member | Tasks |
|---|---|
| A | `extract_routes.py` (Next App and Pages routers, Express routes and simple prefixes), `extract_ports.py`. If time: `gitdiff.py`. |
| B | `match.py`: per-kind rules (scripts, env, routes with dynamic-segment normalisation, ports, engines), allow-list, `OK/STALE/SUSPECT`, image-confidence discount. Tests. |
| C | `judge.py`: batched verdicts, schema check, threshold. `patch.py`: unified diff, deterministic suggestions, `git apply --check`. |

**Exit:** the full text pipeline runs on one fixture with `--no-llm` and with Gemma 4.
**Scope freeze:** P0 only until the image feature starts in Stage 3 (scripts, env, routes, ports, engines).

## Stage 3 — Integration, image claims, packaging (4:00–5:00)

| Member | Tasks |
|---|---|
| A | `scripts/drift.py` CLI wiring (`scan`, `--diff`, `--no-llm`, `--no-images`, `--config`). `gitdiff.py` if not done. Start building the `next_app` fixture and its screenshots early. |
| B | `extract_images.py` (find local images, size and count caps, hash cache, convert vision output to claims, feed the matcher). `report.py` (JSON and Markdown, image findings, model line, exit codes). `samples.py` and `.driftrc` only if ahead. |
| C | `vision.py` (vision prompt, JSON validation, empty/low-quality handling) and `prompts.md` vision section. `SKILL.md` finalised and validated. Test the skill with a real agent on a web repo. |

**Exit:** one command produces a report with text and image findings and patches; the skill loads in an agent. Each person reviews a teammate's PR.

## Stage 4 — Parallel testing and benchmark (5:00–6:15)

Testing is split across all three. Nobody only tests their own work, and each person owns one model size.

| Member | Fixture (text + 2 screenshots, with decoys) | Real-repo run | Model-size benchmark | Break-test target |
|---|---|---|---|---|
| A | `next_app` | A real public Next.js repo | `gemma-4-31b-it` (API) | B's matcher and image finder (dynamic routes, prefixes, huge or tiny images) |
| B | `express_api` | A real public Express repo | `gemma-4-26b-a4b-it` (API) | C's judge, vision and patcher (malformed JSON, blurry screenshots, empty docs) |
| C | `vite_react` | A real public Vite/React repo | Gemma 4 E4B (local Ollama) | A's extractors (route groups, nested routers, dynamic env access) |

**Last 15 minutes, together:** merge the three benchmark result files, fill the per-model-size table in `progress.md`, triage and fix the top bugs in parallel.

## Stage 5 — Polish and submit (6:15–7:00)

| Member | Tasks |
|---|---|
| A | Demo scenario on a real web repo's older commit that includes a route/script rename **and an outdated screenshot**. Record GIF or video. |
| B | README: install, usage, **Why Gemma 4** (map to the track brief), model setup (Gemini API and Ollama), supported stacks, benchmark per model size, limitations. Lint pass, check no secrets in history. |
| C | Final `SKILL.md` re-validation. Re-check local mode. Verify the Gemma 4 license wording and link. Tag `v0.1.0`. |
| All | Fresh-clone install test on a teammate's machine. Submit via "Add Submission" in each eligible category. Update `progress.md`. |

---

## Contingency Rules

| If… | Then… |
|---|---|
| Vision reads are unreliable | Keep only high-confidence image claims; demo with clean terminal screenshots |
| Gemini API compat endpoint lacks image input or JSON mode | Use the native Google SDK adapter in `llm.py` |
| Rate-limited | Use each member's own key, the cache, 26B-A4B, or local E4B; `--no-llm` for clear-cut claims |
| Express routers get messy | Same-file prefixes only; others become SUSPECT |
| Behind at 4:00 | Cut diff mode, `.driftrc`, samples, components, Markdown report; **protect image claims and the model-size benchmark** |
