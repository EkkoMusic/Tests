import { getCollection, type CollectionEntry } from 'astro:content';
import type { CategoryId } from '../data/categories';

export type Project = CollectionEntry<'projects'>;

/** Tous les projets, triés par featuredOrder. Filtre optionnel par catégorie. */
export async function getProjects(category?: CategoryId): Promise<Project[]> {
  const all = await getCollection('projects', (p) => !category || p.data.categories.includes(category));
  return all.sort((a, b) => a.data.featuredOrder - b.data.featuredOrder);
}

/** Projets mis en avant sur la homepage. */
export async function getFeaturedProjects(category?: CategoryId): Promise<Project[]> {
  return (await getProjects(category)).filter((p) => p.data.featured);
}

export const projectHref = (p: Project) => `/work/${p.data.slug}/`;

/** "Environment · 3D · 2025" */
export const projectMeta = (p: Project) =>
  [...p.data.disciplines, p.data.year].filter(Boolean).join(' · ');
