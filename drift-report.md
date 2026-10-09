# drift-report — next_app

Project type: `next_app`  
Findings: **17** (STALE 5, SUSPECT 2, OK 10)
Model: `gemma-4-31b-it (disabled: --no-llm)` (api)

| Status | Doc | Line | Claim | Reason |
|---|---|---|---|---|
| STALE | api.md | 3 | npm run seed | no script named `seed` in package.json |
| OK | api.md | 4 | pnpm build | script `build` exists in package.json |
| STALE | api.md | 5 | GET /api/orders` | route /api/orders not found in code |
| OK | README.md | 7 | npm install | built-in npm script |
| OK | README.md | 9 | node 20.11.0 | node 20.11.0 satisfies engines (>=20) |
| STALE | README.md | 16 | npm run serve | no script named `serve` in package.json |
| OK | README.md | 19 | localhost:3000 | port 3000 found in code |
| OK | README.md | 23 | GET /api/users` | GET /api/users exists in code |
| OK | README.md | 24 | POST /api/users` | POST /api/users exists in code |
| SUSPECT | README.md | 25 | GET /api/v2/users` | similar route exists: /api/users |
| OK | README.md | 26 | fetch('/api/users/:id') | route /api/users/:id exists in code |
| OK | README.md | 26 | /api/users/:id | route /api/users/:id exists in code |
| STALE | README.md | 30 | STRIPE_SECRET_KEY=sk_live_secret | env var STRIPE_SECRET_KEY not found in code |
| OK | README.md | 31 | DATABASE_URL=postgresql://demo | env var DATABASE_URL present in code |
| OK | README.md | 32 | NEXT_PUBLIC_API_URL=https://api.example.com | env var NEXT_PUBLIC_API_URL present in code |
| STALE | README.md | 33 | port 4000 | port 4000 not found in code |
| SUSPECT | README.md | 35 | node 16.20.0 | repo requires >=20, docs say 16.20.0 |

## Patches

_No patches generated._
