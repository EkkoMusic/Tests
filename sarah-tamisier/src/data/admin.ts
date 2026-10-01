/**
 * Espace d'administration (éditeur visuel des projets).
 *
 * Le site est statique : il n'y a pas de serveur pour vérifier un mot de passe.
 * Le mot de passe n'est donc stocké ici que sous forme d'empreinte (PBKDF2-SHA256),
 * jamais en clair. Il sert de porte d'entrée et chiffre, sur chaque appareil,
 * le jeton GitHub qui permet réellement d'enregistrer les modifications.
 *
 * Changer le mot de passe : générer une nouvelle empreinte avec
 *   node scripts/admin-password.mjs "nouveau mot de passe"
 * et remplacer le bloc `password` ci-dessous.
 */
export const admin = {
  password: {
    salt: '2978bd89656cf6b89679954e8ab60fe9',
    iterations: 310000,
    hash: 'aafcfc051614cba0e8b262c13318830987a427e61927b13edda641ea0302446c',
  },
  // Dépôt dans lequel l'éditeur enregistre les modifications (déploiement automatique).
  repo: { owner: 'EkkoMusic', name: 'Tests', branch: 'main', dir: 'sarah-tamisier' },
} as const;
