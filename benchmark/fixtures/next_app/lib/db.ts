const databaseUrl = process.env.DATABASE_URL;
const publicApiUrl = process.env.NEXT_PUBLIC_API_URL;
const cacheHost = process.env.CACHE_HOST;

export function config() {
  return { databaseUrl, publicApiUrl, cacheHost };
}
