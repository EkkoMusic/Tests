# Sarah Tamisier — Portfolio

Site statique [Astro](https://astro.build) : HTML pur, zéro JavaScript côté client, images optimisées au build.

```bash
npm install
npm run dev       # http://localhost:4321/Tests/sarah-tamisier/
npm run build     # génère dist/
npm run check     # vérification TypeScript
```

## Ajouter / réordonner un projet

1. Déposer le visuel dans `src/assets/projects/<slug>/cover.jpg` (JPG/PNG haute définition, idéalement ≥ 2400 px de large).
2. Créer `src/content/projects/<slug>.md` (copier un fichier existant).
3. `featured: true` pour l'afficher dans Selected Work, `featuredOrder` pour l'ordre.

La page `/work/<slug>/` est générée automatiquement. Aucune modification de la homepage n'est nécessaire.

## Où modifier quoi

| Quoi | Fichier |
|---|---|
| Textes (hero, about, contact, SEO, réseaux) | `src/data/site.ts` |
| Couleurs, typographies, espacements | `src/styles/global.css` (variables `:root`) |
| Catégories (filtres du hero, ordre) | `src/data/categories.ts` |
| Rythme de la grille | `src/components/ProjectGrid.astro` |
| Domaine et chemin de base | `astro.config.mjs` (`SITE_URL`, `BASE_PATH`) |

Les images `PLACEHOLDER` se régénèrent avec `npm run placeholders`.
