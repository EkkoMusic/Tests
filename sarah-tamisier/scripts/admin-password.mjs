// Génère l'empreinte d'un nouveau mot de passe admin pour src/data/admin.ts.
// Usage : node scripts/admin-password.mjs "nouveau mot de passe"
import { pbkdf2Sync, randomBytes } from 'node:crypto';

const password = process.argv[2];
if (!password) {
  console.error('Usage : node scripts/admin-password.mjs "nouveau mot de passe"');
  process.exit(1);
}
const salt = randomBytes(16).toString('hex');
const iterations = 310000;
const hash = pbkdf2Sync(password, Buffer.from(salt, 'hex'), iterations, 32, 'sha256').toString('hex');
console.log(`  password: {\n    salt: '${salt}',\n    iterations: ${iterations},\n    hash: '${hash}',\n  },`);
