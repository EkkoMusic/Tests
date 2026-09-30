/**
 * Tous les textes éditables du site au même endroit.
 * Tout est PROVISOIRE (copywriting à retravailler en phase 2).
 */
export const site = {
  name: 'Sarah Tamisier',
  lang: 'en',
  locale: 'en_GB',

  seo: {
    title: 'Sarah Tamisier — Illustrator, Concept Artist & Designer',
    description:
      'Portfolio of Sarah Tamisier, illustrator and designer: concept art, visual development, illustration and product collection design.',
    ogImage: '/og-default.jpg',
  },

  nav: [
    { label: 'Work', href: '/#work' },
    { label: 'About', href: '/#about' },
    { label: 'Contact', href: '/#contact' },
  ],

  hero: {
    // Disciplines affichées dans le hero : ajouter / retirer / reformuler librement.
    disciplines: ['Illustration', 'Concept Art', 'Product Design & Development'],
    // Phrase courte optionnelle (mettre '' pour la masquer).
    statement: 'Illustrator & designer working across imaginary worlds and physical objects.',
  },

  work: {
    title: 'Selected Work',
  },

  about: {
    title: 'About',
    paragraphs: [
      'Sarah Tamisier is an illustrator and designer based in Brittany, France.',
      'For the past seven years, she has worked across illustration, product design and collection development.',
      'She is currently extending her practice into concept art and visual development, combining digital painting and 3D workflows.',
    ],
    moreLabel: 'More about Sarah',
    moreHref: '/about/',
  },

  contact: {
    title: ['Have a project?', 'Let’s talk.'],
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
