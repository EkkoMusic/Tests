// Catégories du portfolio, dans l'ordre d'affichage (la première est active par défaut).
// Elles servent de filtres cliquables dans le hero.
export const categories = [
  // anchor : ancre d'URL (ex. /#illustration), pour partager une catégorie.
  { id: 'product-design', anchor: 'design-produit', label: 'Design produit & développement' },
  { id: 'illustration', anchor: 'illustration', label: 'Illustration' },
  { id: 'concept-art', anchor: 'concept-art', label: 'Concept art' },
] as const;

export type CategoryId = (typeof categories)[number]['id'];
export const categoryIds = categories.map((c) => c.id) as [CategoryId, ...CategoryId[]];
export const categoryLabel = (id: CategoryId) => categories.find((c) => c.id === id)!.label;
