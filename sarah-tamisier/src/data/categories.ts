// Univers du portfolio. Sert au modèle de données et, plus tard, aux filtres
// (ALL / CONCEPT ART + ILLUSTRATION / DESIGN + COLLECTIONS).
export const categories = {
  'concept-art': { label: 'Concept Art & Illustration' },
  design: { label: 'Design & Collections' },
} as const;

export type CategoryId = keyof typeof categories;
export const categoryIds = Object.keys(categories) as [CategoryId, ...CategoryId[]];
