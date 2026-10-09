# drift-report — adamas-care-website

Project type: `next_app`  
Findings: **171** (STALE 88, SUSPECT 5, OK 78)
Model: `gemma-4-31b-it (disabled: --no-llm)` (api)

| Status | Doc | Line | Claim | Reason |
|---|---|---|---|---|
| OK | MOBILE_APP_INTEGRATION.md | 15 | URL=the | env var 'URL' found in code or .env.example |
| STALE | MOBILE_APP_INTEGRATION.md | 16 | localhost:3099 | port 3099 not found in any detected port |
| OK | MOBILE_APP_INTEGRATION.md | 38 | POST /api/auth/login | route POST /api/auth/login matches code route |
| STALE | MOBILE_APP_INTEGRATION.md | 38 | /api/auth/login   {  | route '/api/auth/login   { ' not found in code routes |
| OK | MOBILE_APP_INTEGRATION.md | 48 | GET /api/auth/me | route GET /api/auth/me matches code route |
| STALE | MOBILE_APP_INTEGRATION.md | 48 | /api/auth/me   → 200 {  | route '/api/auth/me   → 200 { ' not found in code routes |
| OK | MOBILE_APP_INTEGRATION.md | 53 | POST /api/auth/refresh | route POST /api/auth/refresh matches code route |
| STALE | MOBILE_APP_INTEGRATION.md | 53 | /api/auth/refresh     (sends gracesalon_refresh cookie) | route '/api/auth/refresh     (sends gracesalon_refresh cookie)' not found in code routes |
| OK | MOBILE_APP_INTEGRATION.md | 69 | POST /api/auth/logout | route POST /api/auth/logout matches code route |
| STALE | MOBILE_APP_INTEGRATION.md | 69 | /api/auth/logout            → {message: | route '/api/auth/logout            → {message:' not found in code routes |
| STALE | MOBILE_APP_INTEGRATION.md | 70 | POST /api/auth/logout-everywhere | route 'POST /api/auth/logout-everywhere' not found in code routes |
| STALE | MOBILE_APP_INTEGRATION.md | 70 | /api/auth/logout-everywhere → {message: | route '/api/auth/logout-everywhere → {message:' not found in code routes |
| OK | MOBILE_APP_INTEGRATION.md | 72 | POST /api/devices/unregister | route POST /api/devices/unregister matches code route |
| OK | MOBILE_APP_INTEGRATION.md | 72 | /api/devices/unregister | route ? /api/devices/unregister matches code route |
| OK | MOBILE_APP_INTEGRATION.md | 92 | POST /api/auth/register | route POST /api/auth/register matches code route |
| STALE | MOBILE_APP_INTEGRATION.md | 92 | /api/auth/register   { name, email, password, gender, whatsappNumber? } | route '/api/auth/register   { name, email, password, gender, whatsappNumber? }' not found in code routes |
| OK | MOBILE_APP_INTEGRATION.md | 102 | POST /api/auth/verify-email | route POST /api/auth/verify-email matches code route |
| STALE | MOBILE_APP_INTEGRATION.md | 102 | /api/auth/verify-email  {  | route '/api/auth/verify-email  { ' not found in code routes |
| OK | MOBILE_APP_INTEGRATION.md | 105 | POST /api/auth/verify-email | route POST /api/auth/verify-email matches code route |
| STALE | MOBILE_APP_INTEGRATION.md | 105 | /api/auth/verify-email  {  | route '/api/auth/verify-email  { ' not found in code routes |
| OK | MOBILE_APP_INTEGRATION.md | 118 | POST /api/auth/forgot-password | route POST /api/auth/forgot-password matches code route |
| STALE | MOBILE_APP_INTEGRATION.md | 118 | /api/auth/forgot-password   {  | route '/api/auth/forgot-password   { ' not found in code routes |
| OK | MOBILE_APP_INTEGRATION.md | 125 | POST /api/auth/reset-password | route POST /api/auth/reset-password matches code route |
| STALE | MOBILE_APP_INTEGRATION.md | 125 | /api/auth/reset-password    {  | route '/api/auth/reset-password    { ' not found in code routes |
| STALE | MOBILE_APP_INTEGRATION.md | 141 | GET /api/bookings | route 'GET /api/bookings' not found in code routes |
| STALE | MOBILE_APP_INTEGRATION.md | 141 | /api/bookings | route '/api/bookings' not found in code routes |
| STALE | MOBILE_APP_INTEGRATION.md | 146 | POST /api/bookings | route 'POST /api/bookings' not found in code routes |
| STALE | MOBILE_APP_INTEGRATION.md | 146 | /api/bookings | route '/api/bookings' not found in code routes |
| STALE | MOBILE_APP_INTEGRATION.md | 167 | PATCH /api/bookings/:id | route 'PATCH /api/bookings/:id' not found in code routes |
| STALE | MOBILE_APP_INTEGRATION.md | 167 | /api/bookings/:id    {  | route '/api/bookings/:id    { ' not found in code routes |
| STALE | MOBILE_APP_INTEGRATION.md | 174 | GET /api/availability?employeeId=arjun-mehta&date=2026-10-05 | route 'GET /api/availability?employeeId=arjun-mehta&date=2026-10-05' not found in code routes |
| STALE | MOBILE_APP_INTEGRATION.md | 174 | /api/availability?employeeId=arjun-mehta&date=2026-10-05 | route '/api/availability?employeeId=arjun-mehta&date=2026-10-05' not found in code routes |
| STALE | MOBILE_APP_INTEGRATION.md | 183 | POST /api/waitlist | route 'POST /api/waitlist' not found in code routes |
| STALE | MOBILE_APP_INTEGRATION.md | 183 | /api/waitlist   { employeeId, slotStart, slotEnd, slotDate?, serviceId? } | route '/api/waitlist   { employeeId, slotStart, slotEnd, slotDate?, serviceId? }' not found in code routes |
| STALE | MOBILE_APP_INTEGRATION.md | 187 | GET /api/waitlist/me | route 'GET /api/waitlist/me' not found in code routes |
| STALE | MOBILE_APP_INTEGRATION.md | 187 | /api/waitlist/me            → {  | route '/api/waitlist/me            → { ' not found in code routes |
| STALE | MOBILE_APP_INTEGRATION.md | 188 | GET /api/waitlist?... | route 'GET /api/waitlist?...' not found in code routes |
| STALE | MOBILE_APP_INTEGRATION.md | 188 | /api/waitlist?...           → {  | route '/api/waitlist?...           → { ' not found in code routes |
| STALE | MOBILE_APP_INTEGRATION.md | 190 | POST /api/waitlist/:id/claim | route 'POST /api/waitlist/:id/claim' not found in code routes |
| STALE | MOBILE_APP_INTEGRATION.md | 190 | /api/waitlist/:id/claim | route '/api/waitlist/:id/claim' not found in code routes |
| OK | MOBILE_APP_INTEGRATION.md | 203 | POST /api/devices/register | route POST /api/devices/register matches code route |
| STALE | MOBILE_APP_INTEGRATION.md | 203 | /api/devices/register    {  | route '/api/devices/register    { ' not found in code routes |
| OK | MOBILE_APP_INTEGRATION.md | 206 | POST /api/devices/unregister | route POST /api/devices/unregister matches code route |
| STALE | MOBILE_APP_INTEGRATION.md | 206 | /api/devices/unregister  {  | route '/api/devices/unregister  { ' not found in code routes |
| OK | MOBILE_APP_INTEGRATION.md | 213 | POST /api/devices/register | route POST /api/devices/register matches code route |
| OK | MOBILE_APP_INTEGRATION.md | 213 | /api/devices/register | route ? /api/devices/register matches code route |
| OK | MOBILE_APP_INTEGRATION.md | 215 | POST /api/devices/unregister | route POST /api/devices/unregister matches code route |
| OK | MOBILE_APP_INTEGRATION.md | 215 | /api/devices/unregister | route ? /api/devices/unregister matches code route |
| STALE | MOBILE_APP_INTEGRATION.md | 252 | PUT /api/auth/profile | route 'PUT /api/auth/profile' not found in code routes |
| STALE | MOBILE_APP_INTEGRATION.md | 252 | /api/auth/profile | route '/api/auth/profile' not found in code routes |
| OK | MOBILE_APP_INTEGRATION.md | 260 | /api/services | route ? /api/services matches code route |
| OK | MOBILE_APP_INTEGRATION.md | 261 | /api/employees | route ? /api/employees matches code route |
| OK | MOBILE_APP_INTEGRATION.md | 261 | /api/testimonials | route ? /api/testimonials matches code route |
| OK | MOBILE_APP_INTEGRATION.md | 261 | /api/suggest | route ? /api/suggest matches code route |
| STALE | MOBILE_APP_INTEGRATION.md | 261 | /api/loyalty* | route '/api/loyalty*' not found in code routes |
| STALE | MOBILE_APP_INTEGRATION.md | 262 | /api/admin/* | route '/api/admin/*' not found in code routes |
| OK | MOBILE_APP_INTEGRATION.md | 278 | GET /api/cron/reminders | route GET /api/cron/reminders matches code route |
| OK | MOBILE_APP_INTEGRATION.md | 278 | /api/cron/reminders | route ? /api/cron/reminders matches code route |
| STALE | MOBILE_APP_INTEGRATION.md | 300 | /api/** | route '/api/**' not found in code routes |
| OK | MOBILE_APP_INTEGRATION.md | 302 | /api/cron/reminders | route ? /api/cron/reminders matches code route |
| OK | MOBILE_APP_INTEGRATION.md | 312 | /api/auth/me | route ? /api/auth/me matches code route |
| STALE | progress.md | 14 | /api/auth/register/route.ts | route '/api/auth/register/route.ts' not found in code routes |
| STALE | progress.md | 15 | /api/auth/verify-email/route.ts | route '/api/auth/verify-email/route.ts' not found in code routes |
| STALE | progress.md | 16 | /api/bookings/[id]/route.ts | route '/api/bookings/[id]/route.ts' not found in code routes |
| STALE | progress.md | 17 | /api/waitlist/[id]/claim/route.ts | route '/api/waitlist/[id]/claim/route.ts' not found in code routes |
| STALE | progress.md | 22 | /api/auth/forgot-password/route.ts | route '/api/auth/forgot-password/route.ts' not found in code routes |
| STALE | progress.md | 23 | /api/auth/reset-password/route.ts | route '/api/auth/reset-password/route.ts' not found in code routes |
| STALE | progress.md | 26 | /api/auth/register/route.ts | route '/api/auth/register/route.ts' not found in code routes |
| STALE | progress.md | 27 | /api/auth/verify-email/route.ts | route '/api/auth/verify-email/route.ts' not found in code routes |
| STALE | progress.md | 36 | /api/auth/profile | route '/api/auth/profile' not found in code routes |
| OK | progress.md | 36 | /api/auth/me | route ? /api/auth/me matches code route |
| STALE | progress.md | 50 | /api/admin/whatsapp-logs/route.ts | route '/api/admin/whatsapp-logs/route.ts' not found in code routes |
| OK | progress.md | 63 | /api/auth/forgot-password | route ? /api/auth/forgot-password matches code route |
| OK | progress.md | 63 | /api/auth/reset-password | route ? /api/auth/reset-password matches code route |
| OK | progress.md | 63 | /api/auth/register | route ? /api/auth/register matches code route |
| OK | progress.md | 63 | /api/auth/verify-email | route ? /api/auth/verify-email matches code route |
| STALE | progress.md | 68 | /api/cron/reminders/route.ts | route '/api/cron/reminders/route.ts' not found in code routes |
| STALE | progress.md | 73 | /api/bookings/route.ts | route '/api/bookings/route.ts' not found in code routes |
| OK | progress.md | 80 | POST /api/auth/forgot-password | route POST /api/auth/forgot-password matches code route |
| OK | progress.md | 80 | /api/auth/forgot-password | route ? /api/auth/forgot-password matches code route |
| OK | progress.md | 81 | POST /api/auth/reset-password | route POST /api/auth/reset-password matches code route |
| OK | progress.md | 81 | /api/auth/reset-password | route ? /api/auth/reset-password matches code route |
| STALE | progress.md | 85 | curl GET against | route 'curl GET against' not found in code routes |
| OK | progress.md | 94 | POST /api/auth/reset-password | route POST /api/auth/reset-password matches code route |
| OK | progress.md | 94 | /api/auth/reset-password | route ? /api/auth/reset-password matches code route |
| OK | progress.md | 95 | POST /api/auth/forgot-password | route POST /api/auth/forgot-password matches code route |
| OK | progress.md | 95 | /api/auth/forgot-password | route ? /api/auth/forgot-password matches code route |
| OK | progress.md | 96 | POST /api/auth/forgot-password | route POST /api/auth/forgot-password matches code route |
| OK | progress.md | 96 | /api/auth/forgot-password | route ? /api/auth/forgot-password matches code route |
| OK | progress.md | 108 | npm test | script 'test' exists in package.json |
| OK | progress.md | 111 | POST /api/auth/register | route POST /api/auth/register matches code route |
| OK | progress.md | 111 | /api/auth/register | route ? /api/auth/register matches code route |
| OK | progress.md | 112 | POST /api/auth/verify-email | route POST /api/auth/verify-email matches code route |
| OK | progress.md | 112 | /api/auth/verify-email | route ? /api/auth/verify-email matches code route |
| STALE | progress.md | 113 | /api/admin/whatsapp-logs | route '/api/admin/whatsapp-logs' not found in code routes |
| STALE | progress.md | 114 | POST /api/auth/profile | route 'POST /api/auth/profile' not found in code routes |
| STALE | progress.md | 114 | /api/auth/profile | route '/api/auth/profile' not found in code routes |
| OK | progress.md | 152 | /api/devices/register | route ? /api/devices/register matches code route |
| OK | progress.md | 152 | /api/devices/unregister | route ? /api/devices/unregister matches code route |
| STALE | progress.md | 153 | :30 | port 30 not found in any detected port |
| OK | progress.md | 177 | /api/devices/register | route ? /api/devices/register matches code route |
| OK | progress.md | 189 | npm test | script 'test' exists in package.json |
| STALE | progress.md | 202 | /api/auth, app/reset-password, lib/email, lib/notify: no WhatsApp send path (only  | route '/api/auth, app/reset-password, lib/email, lib/notify: no WhatsApp send path (only ' not found in code routes |
| STALE | progress.md | 204 | :78 | port 78 not found in any detected port |
| STALE | progress.md | 206 | POST /api/bookings | route 'POST /api/bookings' not found in code routes |
| STALE | progress.md | 206 | /api/bookings (userId set) →  | route '/api/bookings (userId set) → ' not found in code routes |
| OK | progress.md | 221 | NODE_ENV=production | env var 'NODE_ENV' is allowlisted |
| STALE | progress.md | 225 | /api/devices/* | route '/api/devices/*' not found in code routes |
| OK | progress.md | 226 | npm test | script 'test' exists in package.json |
| OK | progress.md | 289 | npm run dev | script 'dev' exists in package.json |
| STALE | progress.md | 292 | localhost:3000 | port 3000 not found in any detected port |
| STALE | progress.md | 292 | :3000 | port 3000 not found in any detected port |
| STALE | progress.md | 292 | curl GET -s | route 'curl GET -s' not found in code routes |
| STALE | progress.md | 292 | /api/auth/forgot-password -H  | route '/api/auth/forgot-password -H ' not found in code routes |
| STALE | progress.md | 294 | localhost:3000 | port 3000 not found in any detected port |
| STALE | progress.md | 294 | :3000 | port 3000 not found in any detected port |
| STALE | progress.md | 294 | curl GET -s | route 'curl GET -s' not found in code routes |
| STALE | progress.md | 294 | /api/auth/forgot-password -H  | route '/api/auth/forgot-password -H ' not found in code routes |
| STALE | progress.md | 299 | POST /api/auth/login, | route 'POST /api/auth/login,' not found in code routes |
| STALE | progress.md | 299 | /api/auth/login, keep cookies) | route '/api/auth/login, keep cookies)' not found in code routes |
| STALE | progress.md | 300 | localhost:3000 | port 3000 not found in any detected port |
| STALE | progress.md | 300 | :3000 | port 3000 not found in any detected port |
| STALE | progress.md | 300 | curl GET -s | route 'curl GET -s' not found in code routes |
| STALE | progress.md | 300 | /api/devices/register \ | route '/api/devices/register \' not found in code routes |
| STALE | progress.md | 309 | localhost:3000 | port 3000 not found in any detected port |
| STALE | progress.md | 309 | :3000 | port 3000 not found in any detected port |
| STALE | progress.md | 309 | curl GET -s | route 'curl GET -s' not found in code routes |
| OK | progress.md | 309 | /api/cron/reminders | route ? /api/cron/reminders matches code route |
| OK | progress.md | 323 | npm run build | script 'build' exists in package.json |
| OK | progress.md | 323 | npm run build | script 'build' exists in package.json |
| OK | progress.md | 323 | npm test | script 'test' exists in package.json |
| OK | progress.md | 324 | npm run build | script 'build' exists in package.json |
| OK | progress.md | 324 | npm install | 'install' is a built-in npm script |
| OK | progress.md | 325 | /api/cron/reminders | route ? /api/cron/reminders matches code route |
| OK | progress.md | 335 | /api/auth/google | route ? /api/auth/google matches code route |
| STALE | progress.md | 342 | RESEND_BASE_URL=http://127.0.0.1:8099 | env var 'RESEND_BASE_URL' not found in code or .env.example |
| STALE | progress.md | 342 | :8099 | port 8099 not found in any detected port |
| OK | progress.md | 345 | /api/cron/reminders | route ? /api/cron/reminders matches code route |
| STALE | progress.md | 349 | /api/admin/whatsapp-logs | route '/api/admin/whatsapp-logs' not found in code routes |
| OK | README.md | 63 | npm install | 'install' is a built-in npm script |
| SUSPECT | README.md | 89 | npm run db | script 'db' similar to existing 'db:seed' (similarity=0.85) |
| OK | README.md | 94 | npm run dev | script 'dev' exists in package.json |
| STALE | README.md | 94 | localhost:3000 | port 3000 not found in any detected port |
| STALE | README.md | 94 | :3000 | port 3000 not found in any detected port |
| OK | README.md | 99 | npm run build | script 'build' exists in package.json |
| OK | README.md | 99 | npm run start | script 'start' exists in package.json |
| OK | README.md | 140 | npm run dev | script 'dev' exists in package.json |
| OK | README.md | 141 | npm run build | script 'build' exists in package.json |
| OK | README.md | 141 | npm run start | script 'start' exists in package.json |
| OK | README.md | 142 | npm run lint | script 'lint' exists in package.json |
| OK | README.md | 143 | npm run test | script 'test' exists in package.json |
| SUSPECT | README.md | 144 | npm run db | script 'db' similar to existing 'db:seed' (similarity=0.85) |
| SUSPECT | README.md | 145 | npm run db | script 'db' similar to existing 'db:seed' (similarity=0.85) |
| SUSPECT | README.md | 146 | npm run db | script 'db' similar to existing 'db:seed' (similarity=0.85) |
| SUSPECT | README.md | 147 | npm run db | script 'db' similar to existing 'db:seed' (similarity=0.85) |
| STALE | SECURITY-FIXES.md | 14 | PATCH /api/bookings/<id | route 'PATCH /api/bookings/<id' not found in code routes |
| STALE | SECURITY-FIXES.md | 14 | /api/bookings/<id> | route '/api/bookings/<id>' not found in code routes |
| STALE | SECURITY-FIXES.md | 23 | /api/bookings/[id]/route.ts | route '/api/bookings/[id]/route.ts' not found in code routes |
| STALE | SECURITY-FIXES.md | 62 | /api/** | route '/api/**' not found in code routes |
| STALE | SECURITY-FIXES.md | 84 | /api/cron/reminders/route.ts | route '/api/cron/reminders/route.ts' not found in code routes |
| STALE | SECURITY-FIXES.md | 151 | npm audit | script 'audit' not found in package.json |
| STALE | SECURITY-FIXES.md | 160 | npm audit | script 'audit' not found in package.json |
| STALE | SECURITY-FIXES.md | 164 | npm audit | script 'audit' not found in package.json |
| OK | SECURITY-FIXES.md | 172 | npm install | 'install' is a built-in npm script |
| OK | SECURITY-FIXES.md | 178 | npm run build | script 'build' exists in package.json |
| OK | SECURITY-FIXES.md | 178 | npm run lint | script 'lint' exists in package.json |
| OK | SECURITY-FIXES.md | 179 | npm test | script 'test' exists in package.json |
| STALE | SECURITY-FIXES.md | 180 | npm audit | script 'audit' not found in package.json |
| OK | SECURITY-FIXES.md | 204 | npm run lint | script 'lint' exists in package.json |
| OK | SECURITY-FIXES.md | 205 | npm test | script 'test' exists in package.json |
| OK | SECURITY-FIXES.md | 206 | npm run build | script 'build' exists in package.json |

## Patches

_No patches generated._
