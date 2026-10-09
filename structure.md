# structure.md — docs-drift-detector (Web Dev Edition, Gemma 4)

## Repository Layout

```
docs-drift-detector/
├── LICENSE                     # MIT, added in the first commit
├── README.md                   # includes "Why Gemma 4" and benchmark per model size
├── SKILL.md                    # Agent Skill entry (frontmatter: name, description)
├── PRD.md / TRD.md / stages.md / structure.md / progress.md
├── .env.example                # DRIFT_BASE_URL, DRIFT_API_KEY, DRIFT_MODEL, DRIFT_FOLD_SYSTEM
├── .driftrc.example.json
├── .gitignore                  # includes .env and .drift_cache/
├── scripts/
│   └── drift.py                # CLI entrypoint (scan, --diff, --no-llm, --no-images, --config)
├── drift/
│   ├── __init__.py
│   ├── models.py               # Fact, Claim (source: text|image), Finding
│   ├── detect.py               # detect web project type (Next / Express / Vite)
│   ├── extract_pkg.py          # package.json scripts, deps, engines, .nvmrc
│   ├── extract_env.py          # process.env / import.meta.env / .env.example
│   ├── extract_routes.py       # Next app/pages routes, Express routes
│   ├── extract_ports.py        # listen(), -p/--port, vite server.port
│   ├── extract_components.py   # React component props (P2)
│   ├── gitdiff.py              # --diff mode: changed facts
│   ├── extract_docs.py         # text claims from Markdown (web patterns)
│   ├── extract_images.py       # find local images in docs, caps, hash cache, build image claims
│   ├── match.py                # per-kind matching (+ image confidence discount)
│   ├── samples.py              # code-sample checks: imports, node --check (P1)
│   ├── llm.py                  # Gemma 4 client: text + image, retry, cache, system-role folding
│   ├── vision.py               # image → JSON claims via Gemma 4 vision
│   ├── judge.py                # prompt build + verdict parsing
│   ├── patch.py                # unified diff + git apply --check (text findings only)
│   └── report.py               # JSON + Markdown output (image findings included)
├── references/
│   ├── prompts.md              # versioned prompts: judge + vision
│   └── schema.json             # output JSON schema
├── benchmark/
│   ├── fixtures/
│   │   ├── next_app/           # Next.js App Router + Prisma + 2 screenshots (Member A)
│   │   ├── express_api/        # Express API + 2 screenshots (Member B)
│   │   └── vite_react/         # Vite + React + 2 screenshots (Member C)
│   ├── expected.json           # ground truth (text and image drifts)
│   ├── run_bench.py            # --model <id> → per-model results
│   └── results/                # one JSON per model size
└── tests/
    ├── test_extract_pkg_env.py      # A
    ├── test_extract_routes_ports.py # A
    ├── test_extract_docs.py         # B
    ├── test_extract_images.py       # B
    ├── test_match.py                # B
    ├── test_llm.py                  # C (text + image, mocked)
    ├── test_vision_judge_patch.py   # C
    └── test_e2e.py                  # all
```

## Module Ownership

| Path | Owner | Cross-tester |
|---|---|---|
| `detect.py`, `extract_pkg.py`, `extract_env.py` | A | C |
| `extract_routes.py`, `extract_ports.py`, `gitdiff.py`, `extract_components.py` (P2) | A | B |
| `scripts/drift.py`, `benchmark/run_bench.py`, `fixtures/next_app` | A | B |
| `extract_docs.py`, `extract_images.py`, `match.py`, `samples.py`, `report.py` | B | A |
| `README.md`, `.driftrc` support, `fixtures/express_api` | B | C |
| `llm.py`, `vision.py`, `judge.py`, `patch.py` | C | B |
| `SKILL.md`, `references/prompts.md`, `fixtures/vite_react` | C | A |
| `models.py`, `references/schema.json` | B (agreed by all in Stage 0) | A, C |

## Data Flow

```
detect ─► (is it a web repo?)
extract_pkg    ─┐
extract_env    ─┤
extract_routes ─┼─► Facts ─┐
extract_ports  ─┘          │
                           ├─► match ──► Findings (OK / STALE / SUSPECT)
extract_docs ───► Claims ──┤                │
extract_images ─► image ───┘                ├─ SUSPECT ─► judge (Gemma 4) ─► verdicts
       ▲          claims                    ▼                                  │
       └── vision.py (Gemma 4 vision)    patch (text only) ◄───────────────────┘
                                            │
                                          report ──► drift-report.json / .md
```

## Branch and PR Convention

- `main` is always runnable.
- Branches: `a/extract-routes`, `b/image-claims`, `c/vision`, and so on.
- Every PR gets one review from a teammate (see the Cross-tester column).
- Commit messages: `feat:`, `fix:`, `test:`, `docs:`.
