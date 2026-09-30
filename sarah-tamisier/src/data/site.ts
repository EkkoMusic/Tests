/**
 * Tous les textes éditables du site au même endroit.
 * Tout est PROVISOIRE (copywriting à retravailler).
 * Les catégories du hero (filtres) se règlent dans ./categories.ts.
 */
export const site = {
  name: 'Sarah Tamisier',
  lang: 'fr',
  locale: 'fr_FR',

  seo: {
    title: 'Sarah Tamisier — Illustratrice, concept artist & designer',
    description:
      'Portfolio de Sarah Tamisier, illustratrice et designer : design produit et collections, illustration, concept art et visual development.',
    ogImage: '/og-default.jpg',
  },

  nav: [
    { label: 'Projets', href: '/#projets' },
    { label: 'À propos', href: '/#a-propos' },
    { label: 'Contact', href: '/#contact' },
  ],

  hero: {
    // Phrase courte optionnelle (mettre '' pour la masquer).
    statement: 'Illustratrice et designer, entre mondes imaginaires et objets bien réels.',
    filtersLabel: 'Afficher les projets par discipline',
    portraitAlt: 'Portrait de Sarah Tamisier, de profil',
  },

  about: {
    title: 'À propos',
    paragraphs: [
      'Je suis illustratrice et designer, installée en Bretagne.',
      'Depuis sept ans, je travaille entre illustration, design produit et développement de collections.',
      'J’élargis aujourd’hui ma pratique au concept art et au visual development, en associant peinture digitale et 3D.',
    ],
    moreLabel: 'En savoir plus',
    moreHref: '/a-propos/',
  },

  contact: {
    title: ['Me contacter'],
    // TODO : adresse e-mail réelle. Ne jamais publier d'adresse postale ni de téléphone.
    email: 'hello@example.com',
    // Mettre l'URL pour afficher un lien, laisser vide pour le masquer.
    socials: [
      { label: 'LinkedIn', href: '' },
      { label: 'ArtStation', href: '' },
      { label: 'Instagram', href: '' },
    ],
  },
} as const;
