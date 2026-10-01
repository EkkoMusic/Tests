import type { APIRoute } from 'astro';
import { parse } from 'yaml';
import { admin } from '../../data/admin';
import { categories } from '../../data/categories';

/**
 * Données brutes des projets (frontmatter tel qu'écrit dans les fichiers .md),
 * lues par l'éditeur visuel pour réécrire les fichiers à l'identique.
 */
const files = import.meta.glob('../../content/projects/*.md', { query: '?raw', import: 'default', eager: true }) as Record<string, string>;

export const GET: APIRoute = () => {
  const projects = Object.entries(files).map(([file, raw]) => {
    const [, front = '', body = ''] = raw.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/) ?? [];
    return {
      path: `${admin.repo.dir}/src/content/projects/${file.split('/').pop()}`,
      data: parse(front) ?? {},
      body,
    };
  });

  return new Response(
    JSON.stringify({
      // Commit à partir duquel ce site a été construit (fourni par GitHub Actions).
      buildSha: process.env.GITHUB_SHA ?? null,
      repo: admin.repo,
      categories: categories.map(({ id, label }) => ({ id, label })),
      projects,
    }),
    { headers: { 'Content-Type': 'application/json' } },
  );
};
