import type { APIRoute } from 'astro';

export const GET: APIRoute = ({ site }) =>
  new Response(`User-agent: *\nAllow: /\n\nSitemap: ${new URL('sitemap-index.xml', new URL(import.meta.env.BASE_URL.replace(/\/?$/, '/'), site)).href}\n`);
