# drift-report — next_app

Project type: `next_app`  
Findings: **21** (STALE 7, SUSPECT 2, OK 12)
Model: `gemma-4-31b-it (disabled: --no-llm)` (api)

| Status | Doc | Line | Claim | Reason |
|---|---|---|---|---|
| STALE | api.md | 3 | npm run seed | script 'seed' not found in package.json |
| OK | api.md | 4 | pnpm build | script 'build' exists in package.json |
| STALE | api.md | 5 | GET /api/orders | route 'GET /api/orders' not found in code routes |
| STALE | api.md | 5 | /api/orders | route '/api/orders' not found in code routes |
| OK | README.md | 7 | npm install | 'install' is a built-in npm script |
| OK | README.md | 9 | node 20.11.0 | claimed node 20.11.0 satisfies engines (>=20) |
| STALE | README.md | 16 | npm run serve | script 'serve' not found in package.json |
| OK | README.md | 19 | localhost:3000 | port 3000 matches detected port |
| OK | README.md | 23 | GET /api/users | route GET /api/users matches code route |
| OK | README.md | 23 | /api/users | route ? /api/users matches code route |
| OK | README.md | 24 | POST /api/users | route POST /api/users matches code route |
| OK | README.md | 24 | /api/users | route ? /api/users matches code route |
| SUSPECT | README.md | 25 | GET /api/v2/users | route '/api/v2/users' similar to existing '/api/users' (possible version prefix change) |
| SUSPECT | README.md | 25 | /api/v2/users | route '/api/v2/users' similar to existing '/api/users' (possible version prefix change) |
| OK | README.md | 26 | fetch('/api/users/:id') | route ? /api/users/:id matches code route |
| OK | README.md | 26 | /api/users/:id | route ? /api/users/:id matches code route |
| STALE | README.md | 30 | STRIPE_SECRET_KEY=sk_live_secret | env var 'STRIPE_SECRET_KEY' not found in code or .env.example |
| OK | README.md | 31 | DATABASE_URL=postgresql://demo | env var 'DATABASE_URL' found in code or .env.example |
| OK | README.md | 32 | NEXT_PUBLIC_API_URL=https://api.example.com | env var 'NEXT_PUBLIC_API_URL' found in code or .env.example |
| STALE | README.md | 33 | port 4000 | port 4000 not found in any detected port |
| STALE | README.md | 35 | node 16.20.0 | claimed node 16.20.0 below required >=20 |

## Patches

_No patches generated._
