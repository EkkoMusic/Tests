# Instructions pour Claude Code

## Workflow obligatoire après chaque modification

Après **chaque modification de fichier**, tu dois systématiquement :

```bash
git add .
git commit -m "description courte du changement"
git push
```

Le site est déployé automatiquement sur https://ekkomusic.github.io/Tests/ via GitHub Actions (~30 secondes après le push).

## Structure du projet

Le site se trouve dans le dossier `4mousquetaires/` :
- `index.html` — page d'accueil
- `css/` — styles
- `js/` — scripts
- `about.html`, `services.html`, etc. — autres pages
