# Contexte du projet — Cagnotte Secrète

## Infrastructure

- **Serveur** : Render.com (Node.js)
- **Base de données** : MongoDB Atlas
- **Variable d'environnement** `MONGODB_URI` déjà configurée sur Render
- **Déploiement automatique** : commit + push sur la branche `main` du repo `EkkoMusic/Tests` → Render redéploie automatiquement

## Structure du repo

```
server.js      → backend Node.js (API, logique serveur)
docs/          → frontend (HTML, CSS, JS) — servi statiquement par le serveur
package.json   → dépendances
```

## Points importants

- Les routes API doivent être dans `server.js` sous `/api/...`
- MongoDB est accessible via `process.env.MONGODB_URI`
- Le frontend dans `docs/` appelle le backend avec des chemins relatifs `/api/...` (pas de localhost)
- Le port est `process.env.PORT` (déjà configuré)
- Le dossier statique servi est `docs/` (pas `public/`)
