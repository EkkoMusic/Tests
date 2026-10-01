import { admin } from '../data/admin';

/**
 * Authentification de l'espace admin, entièrement dans le navigateur.
 * - Le mot de passe est vérifié contre son empreinte PBKDF2 (src/data/admin.ts).
 * - Le jeton GitHub est chiffré (AES-GCM) avec une clé dérivée du mot de passe
 *   et gardé uniquement sur l'appareil (localStorage) : il n'est jamais publié.
 * - Pendant la session (onglet ouvert), le jeton déchiffré vit dans sessionStorage.
 */

const SESSION_KEY = 'st-admin-token';
const VAULT_KEY = 'st-admin-vault';
const enc = new TextEncoder();

const hex = (buf: ArrayBuffer | Uint8Array) =>
  [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, '0')).join('');
const unhex = (s: string) => new Uint8Array(s.match(/../g)!.map((h) => parseInt(h, 16)));

async function pbkdf2(password: string, salt: Uint8Array, iterations: number, usage: 'bits' | 'aes') {
  const base = await crypto.subtle.importKey('raw', enc.encode(password), 'PBKDF2', false, ['deriveBits', 'deriveKey']);
  const params = { name: 'PBKDF2', hash: 'SHA-256', salt, iterations };
  if (usage === 'bits') return crypto.subtle.deriveBits(params, base, 256);
  return crypto.subtle.deriveKey(params, base, { name: 'AES-GCM', length: 256 }, false, ['encrypt', 'decrypt']);
}

export async function checkPassword(password: string): Promise<boolean> {
  const { salt, iterations, hash } = admin.password;
  const bits = (await pbkdf2(password, unhex(salt), iterations, 'bits')) as ArrayBuffer;
  return hex(bits) === hash;
}

interface Vault { salt: string; iv: string; data: string }

function readVault(): Vault | null {
  try { return JSON.parse(localStorage.getItem(VAULT_KEY) ?? 'null'); } catch { return null; }
}

export const hasVault = () => readVault() !== null;

export async function saveVault(password: string, token: string) {
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const key = (await pbkdf2(password, salt, 200000, 'aes')) as CryptoKey;
  const data = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, key, enc.encode(token));
  localStorage.setItem(VAULT_KEY, JSON.stringify({ salt: hex(salt), iv: hex(iv), data: hex(data) }));
}

export async function openVault(password: string): Promise<string | null> {
  const vault = readVault();
  if (!vault) return null;
  try {
    const key = (await pbkdf2(password, unhex(vault.salt), 200000, 'aes')) as CryptoKey;
    const data = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: unhex(vault.iv) }, key, unhex(vault.data));
    return new TextDecoder().decode(data);
  } catch {
    return null;
  }
}

export const forgetVault = () => localStorage.removeItem(VAULT_KEY);

/** Vérifie que le jeton peut écrire dans le dépôt. Renvoie un message d'erreur, ou null. */
export async function checkToken(token: string): Promise<string | null> {
  const { owner, name } = admin.repo;
  try {
    const res = await fetch(`https://api.github.com/repos/${owner}/${name}`, {
      headers: { Authorization: `Bearer ${token}`, Accept: 'application/vnd.github+json' },
    });
    if (res.status === 401) return 'Ce jeton GitHub est invalide ou a expiré.';
    if (!res.ok) return `Ce jeton n’a pas accès au dépôt ${owner}/${name}.`;
    const repo = await res.json();
    if (!repo.permissions?.push) return 'Ce jeton peut lire le dépôt mais pas y écrire (permission « Contents : Read and write » manquante).';
    return null;
  } catch {
    return 'Impossible de joindre GitHub. Vérifiez la connexion.';
  }
}

export const getSessionToken = () => sessionStorage.getItem(SESSION_KEY);
export const startSession = (token: string) => sessionStorage.setItem(SESSION_KEY, token);
export const endSession = () => sessionStorage.removeItem(SESSION_KEY);
