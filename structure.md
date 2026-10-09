# structure.md — docs-drift-detector (Web Dev Edition)

## Repository Layout

```
docs-drift-detector/
├── LICENSE                     # MIT, added in the first commit
├── README.md
├── SKILL.md                    # Agent Skill entry (frontmatter: name, description)
├── PRD.md / TRD.md / stages.md / structure.md / progress.md
├── .env.example                # DRIFT_BASE_URL, DRIFT_API_KEY, DRIFT_MODEL
├── .driftrc.example.json
├── .gitignore                  # includes .env and .drift_cache/
├── scripts/
│   └── drift.py                # CLI entrypoint (scan, --diff, --no-llm, --config)
├── drift/
│   ├── __init__.py
│   ├── models.py               # Fact, Claim, Finding dataclasses
│   ├── detect.py               # detect web project type (Next / Express / Vite)
│   ├── extract_pkg.py          # package.json scripts, deps, engines, .nvmrc
│   ├── extract_env.py          # process.env / import.meta.env / .env.example
│   ├── extract_routes.py       # Next app/pages routes, Express routes
│   ├── extract_ports.py        # listen(), -p/--port, vite server.port
│   ├── extract_components.py   # React component props (P1)
│   ├── gitdiff.py              # --diff mode: changed facts
│   ├── extract_docs.py         # doc claims from Markdown (web patterns)
│   ├── match.py                # per-kind deterministic matching
│   ├── samples.py              # code-sample checks: imports, node --check (P1)
│   ├── llm.py                  # OpenAI-compatible client, retry, cache
│   ├── judge.py                # prompt build + verdict parsing
│   ├── patch.py                # unified diff + git apply --check
│   └── report.py               # JSON + Markdown output
├── references/
│   ├── prompts.md              # versioned prompts
│   └── schema.json             # output JSON schema
├── benchmark/
│   ├── fixtures/
│   │   ├── next_app/           # Next.js App Router + Prisma (Member A)
│   │   ├── express_api/        # Express API (Member B)
│   │   └── vite_react/         # Vite + React (Member C)
│   ├── expected.json           # ground truth
│   └── run_bench.py
└── tests/
    ├── test_extract_pkg_env.py     # A
    ├── test_extract_routes_ports.py# A
    ├── test_extract_docs.py        # B
    ├── test_match.py               # B
    ├── test_llm.py                 # C
    ├── test_judge_patch.py         # C
    └── test_e2e.py                 # all
```

## Module Ownership

| Path | Owner | Cross-tester |
|---|---|---|
| `extract_pkg.py`, `extract_env.py`, `detect.py` | A | C |
| `extract_routes.py`, `extract_ports.py`, `extract_components.py`, `gitdiff.py` | A | B |
| `scripts/drift.py`, `benchmark/run_bench.py`, `fixtures/next_app` | A | B |
| `extract_docs.py`, `match.py`, `samples.py`, `report.py` | B | A |
| `README.md`, `.driftrc` support, `fixtures/express_api` | B | C |
| `llm.py`, `judge.py`, `patch.py` | C | B |
| `SKILL.md`, `references/prompts.md`, `fixtures/vite_react` | C | A |
| `models.py`, `references/schema.json` | B (agreed by all in Stage 0) | A, C |

## Data Flow

```
detect ─► (is it a web repo?)
extract_pkg    ─┐
extract_env    ─┤
extract_routes ─┼─► Facts ─┐
extract_ports  ─┤          ├─► match ──► Findings (OK / STALE / SUSPECT)
extract_comp.  ─┘          │                │
extract_docs ───► Claims ──┘                ├─ SUSPECT ─► judge (llm) ─► verdicts
                                            ▼                              │
                                          patch ◄──────────────────────────┘
                                            │
                                          report ──► drift-report.json / .md
```

## Branch and PR Convention

- `main` is always runnable.
- Branches: `a/extract-routes`, `b/matcher`, `c/judge`, and so on.
- Every PR gets one review from a teammate (see the Cross-tester column).
- Commit messages: `feat:`, `fix:`, `test:`, `docs:`.
