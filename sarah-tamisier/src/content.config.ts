import { defineCollection } from 'astro:content';
import { glob } from 'astro/loaders';
import { z } from 'astro/zod';
import { categoryIds } from './data/categories';

/**
 * Un fichier Markdown = un projet (src/content/projects/*.md).
 * Ajouter ou réordonner un projet ne nécessite aucune modification de la homepage :
 * seuls `featured` et `featuredOrder` décident de ce qui apparaît dans Selected Work.
 */
const projects = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/projects' }),
  schema: ({ image }) =>
    z.object({
      title: z.string(),
      slug: z.string().regex(/^[a-z0-9-]+$/, 'slug : minuscules, chiffres et tirets uniquement'),
      year: z.number().int().optional(),
      category: z.enum(categoryIds),
      disciplines: z.array(z.string()).min(1),
      client: z.string().optional(),
      thumbnail: image(),
      thumbnailAlt: z.string().min(1),
      featured: z.boolean().default(false),
      featuredOrder: z.number().default(999),
      shortDescription: z.string().optional(),
      images: z.array(z.object({ src: image(), alt: z.string().min(1) })).default([]),
      // Optionnel : force la place dans la grille éditoriale (sinon rythme automatique).
      layout: z.enum(['full', 'large', 'small', 'wide', 'medium', 'offset', 'centered']).optional(),
      // true tant que les visuels / textes sont temporaires.
      placeholder: z.boolean().default(false),
    }),
});

export const collections = { projects };
