# Next Demo App

A small Next.js (App Router) demo with a Prisma-backed API.

## Setup

1. `npm install`
2. Copy `.env.example` to `.env` and fill the values.
3. Requires `node 20.11.0` or newer.

## Development

Run the dev server:

```bash
npm run serve
```

Then open `http://localhost:3000` in your browser.

## API

- List users: `GET /api/users`
- Create a user: `POST /api/users`
- Legacy docs: `GET /api/v2/users` returns the paginated list.
- Fetch one user with `fetch('/api/users/:id')`.

## Configuration

Set STRIPE_SECRET_KEY=sk_live_secret in your `.env` file.
Copy DATABASE_URL=postgresql://demo into your env.
Public base URL: NEXT_PUBLIC_API_URL=https://api.example.com
The API listens on `port 4000`.

This project requires node 16.20.0 for the legacy worker.
