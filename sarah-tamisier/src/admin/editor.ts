/**
 * Éditeur visuel du portfolio (chargé uniquement quand l'admin est connecté).
 *
 * On voit la vraie page ; un menu flottant permet de modifier textes et images,
 * d'ajouter, réordonner ou supprimer des projets. « Enregistrer » écrit les
 * fichiers .md et les images dans le dépôt GitHub en un seul commit, ce qui
 * redéploie le site automatiquement.
 */
import './editor.css';
import { WRITE_DENIED, endSession, forgetVault, getSessionToken } from './auth';

interface Img { src: string; alt: string }
interface Data {
  title: string;
  slug: string;
  year?: number;
  categories: string[];
  disciplines: string[];
  client?: string;
  thumbnail: string;
  thumbnailAlt: string;
  featured?: boolean;
  featuredOrder?: number;
  placeholder?: boolean;
  shortDescription?: string;
  images?: Img[];
  [key: string]: unknown;
}
interface Entry { path: string; body: string; data: Data; original: string; isNew?: boolean; deleted?: boolean }
interface Payload {
  buildSha: string | null;
  repo: { owner: string; name: string; branch: string; dir: string };
  categories: { id: string; label: string }[];
  projects: { path: string; data: Data; body: string }[];
}

const token = getSessionToken()!;
const BASE = import.meta.env.BASE_URL.replace(/\/?$/, '/');
const ADMIN_URL = `${BASE}admin/`;

let payload: Payload;
const entries = new Map<string, Entry>(); // par slug
const uploads = new Map<string, Blob>(); // chemin dans le dépôt → image à envoyer
const previews = new Map<string, string>(); // chemin relatif (.md) → URL locale d'aperçu
let originalFiles = new Set<string>(); // images référencées dans la version en ligne
let expectedHead: string | null = null;
let stale = false;
let saving = false;
let leaving = false;
let editing = sessionStorage.getItem('st-admin-mode') !== 'preview';

const projectPage = document.querySelector<HTMLElement>('.project-page[data-slug]');
const pageSlug = projectPage?.dataset.slug;
const isHome = !!document.querySelector('[data-panel]');

/* --------------------------------------------------------------------------
   Utilitaires
   -------------------------------------------------------------------------- */

function h<K extends keyof HTMLElementTagNameMap>(tag: K, attrs: Record<string, string> = {}, ...children: (Node | string)[]) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  node.append(...children);
  return node;
}

/** Recopie l'attribut de style scopé d'Astro (data-astro-cid-…) pour garder le rendu du site. */
function scope<T extends HTMLElement>(node: T, like: Element | null): T {
  const attr = like && [...like.attributes].find((a) => a.name.startsWith('data-astro-cid'));
  if (attr) node.setAttribute(attr.name, '');
  return node;
}

const button = (label: string, action: string, extra = '') =>
  h('button', { type: 'button', class: `st-btn ${extra}`.trim(), 'data-st': action }, label);

function toast(message: string, tone: 'info' | 'ok' | 'error' = 'info') {
  const box = document.querySelector('.st-toasts') ?? document.body.appendChild(h('div', { class: 'st-toasts', 'aria-live': 'polite' }));
  const item = h('div', { class: `st-toast st-toast--${tone}` }, message);
  box.append(item);
  setTimeout(() => item.remove(), tone === 'error' ? 9000 : 5000);
}

const slugify = (s: string) =>
  s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');

const meta = (d: Data) => [...d.disciplines, d.year].filter(Boolean).join(' · ');
const categoryLabel = (id: string) => payload.categories.find((c) => c.id === id)?.label ?? id;

/** Chemin relatif écrit dans le .md → chemin dans le dépôt. */
function repoPath(rel: string) {
  const parts = `${payload.repo.dir}/src/content/projects`.split('/');
  for (const seg of rel.split('/')) {
    if (seg === '..') parts.pop();
    else if (seg && seg !== '.') parts.push(seg);
  }
  return parts.join('/');
}

const filesOf = (d: Data) => [d.thumbnail, ...(d.images ?? []).map((i) => i.src)].map(repoPath);
const isDirty = (e: Entry) => e.deleted || e.isNew || JSON.stringify(e.data) !== e.original;
const dirtyEntries = () => [...entries.values()].filter((e) => isDirty(e) && !(e.isNew && e.deleted));

/* --------------------------------------------------------------------------
   Images
   -------------------------------------------------------------------------- */

function pickFiles(multiple = false): Promise<File[]> {
  return new Promise((resolve) => {
    const input = h('input', { type: 'file', accept: 'image/jpeg,image/png,image/webp' });
    input.multiple = multiple;
    input.addEventListener('change', () => resolve([...(input.files ?? [])]));
    input.click();
  });
}

/** Réduit les très grandes images (max 2800 px) pour garder un dépôt léger. */
async function prepareImage(file: File): Promise<{ blob: Blob; ext: string }> {
  const MAX = 2800;
  const types: Record<string, string> = { 'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp' };
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(1, MAX / Math.max(bitmap.width, bitmap.height));
  if (types[file.type] && scale === 1 && file.size <= 3_000_000) return { blob: file, ext: types[file.type] };

  const canvas = h('canvas');
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  const ctx = canvas.getContext('2d')!;
  const alpha = file.type === 'image/png' || file.type === 'image/webp';
  if (!alpha) { ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, canvas.width, canvas.height); }
  ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  const blob = await new Promise<Blob>((res) => canvas.toBlob((b) => res(b!), alpha ? 'image/webp' : 'image/jpeg', 0.88));
  return { blob, ext: types[blob.type] ?? 'png' };
}

/** Ajoute une image au projet : renvoie le chemin relatif à écrire dans le .md. */
async function addImage(slug: string, file: File, prefix: string) {
  const { blob, ext } = await prepareImage(file);
  const rel = `../../assets/projects/${slug}/${prefix}-${Date.now().toString(36)}${Math.random().toString(36).slice(2, 5)}.${ext}`;
  uploads.set(repoPath(rel), blob);
  previews.set(rel, URL.createObjectURL(blob));
  return rel;
}

/** Remplace l'image (picture ou img) d'un conteneur par l'aperçu local, si l'image a changé. */
function showPreview(container: Element, rel: string, alt: string) {
  const src = previews.get(rel);
  const current = container.querySelector('picture, img');
  if (!src) {
    current?.querySelector('img')?.setAttribute('alt', alt);
    if (current instanceof HTMLImageElement) current.alt = alt;
    return;
  }
  if (current instanceof HTMLImageElement && current.src === src) return;
  const img = scope(h('img', { src, alt, class: 'st-preview' }), current);
  if (current) current.replaceWith(img);
  else container.prepend(img);
}

/* --------------------------------------------------------------------------
   Écriture des fichiers .md
   -------------------------------------------------------------------------- */

const ORDER = ['title', 'slug', 'year', 'categories', 'disciplines', 'client', 'thumbnail', 'thumbnailAlt',
  'featured', 'featuredOrder', 'placeholder', 'shortDescription', 'images', 'layout'];
const q = (v: unknown) => JSON.stringify(v); // une chaîne JSON est une chaîne YAML valide

function toMarkdown(e: Entry) {
  const d = e.data;
  const lines = ['---'];
  for (const key of [...ORDER, ...Object.keys(d).filter((k) => !ORDER.includes(k))]) {
    const v = d[key];
    if (v === undefined || v === null || v === '' || (Array.isArray(v) && v.length === 0)) continue;
    if (key === 'images') {
      lines.push('images:');
      for (const img of v as Img[]) lines.push(`  - src: ${q(img.src)}`, `    alt: ${q(img.alt)}`);
    } else if (Array.isArray(v)) lines.push(`${key}: [${v.map(q).join(', ')}]`);
    else if (typeof v === 'object' || typeof v === 'string') lines.push(`${key}: ${q(v)}`);
    else lines.push(`${key}: ${v}`);
  }
  lines.push('---');
  return `${lines.join('\n')}\n${e.body ?? ''}`;
}

/* --------------------------------------------------------------------------
   GitHub
   -------------------------------------------------------------------------- */

async function gh(path: string, body?: unknown, method = body ? 'POST' : 'GET') {
  const { owner, name } = payload.repo;
  const res = await fetch(`https://api.github.com/repos/${owner}/${name}${path}`, {
    method,
    headers: { Authorization: `Bearer ${token}`, Accept: 'application/vnd.github+json', 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401) throw new Error('Le jeton GitHub a expiré ou a été révoqué : reconnectez-vous depuis la page admin.');
  if (res.status === 403 || (res.status === 404 && method !== 'GET')) {
    // Jeton sans droit d'écriture : on l'oublie pour qu'un jeton corrigé soit demandé à la prochaine connexion.
    forgetVault();
    throw new Error(`${WRITE_DENIED} Puis reconnectez-vous depuis la page admin.`);
  }
  if (!res.ok) throw new Error(`GitHub a refusé l’enregistrement (erreur ${res.status}).`);
  return res.json();
}

const headSha = async (): Promise<string> => (await gh(`/git/ref/heads/${payload.repo.branch}`)).object.sha;

const toBase64 = (blob: Blob) =>
  new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(',')[1]);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });

async function save() {
  const dirty = dirtyEntries();
  if (!dirty.length) return toast('Aucune modification à enregistrer.');
  if (stale) return toast('Une publication est en cours : rechargez la page dans une minute avant d’enregistrer.', 'error');

  for (const e of dirty.filter((e) => !e.deleted)) {
    const d = e.data;
    const problem = !d.title.trim() ? 'un titre'
      : !d.categories.length ? 'au moins une catégorie'
      : !d.disciplines.length ? 'au moins une discipline'
      : !d.thumbnailAlt.trim() ? 'une description de l’image (texte alternatif)' : null;
    if (problem) return toast(`« ${d.title || d.slug} » : il manque ${problem}.`, 'error');
  }

  saving = true;
  updateBar();
  try {
    const { branch, dir } = payload.repo;
    const head = await headSha();
    if (expectedHead && head !== expectedHead) {
      stale = true;
      throw new Error('Le site a été modifié entre-temps. Rechargez la page dans une minute, puis refaites vos modifications.');
    }
    const base = await gh(`/git/commits/${head}`);

    const live = new Set<string>();
    for (const e of entries.values()) if (!e.deleted) filesOf(e.data).forEach((f) => live.add(f));

    const tree: Record<string, unknown>[] = [];
    for (const [path, blob] of uploads) {
      if (!live.has(path)) continue;
      const { sha } = await gh('/git/blobs', { content: await toBase64(blob), encoding: 'base64' });
      tree.push({ path, mode: '100644', type: 'blob', sha });
    }
    for (const e of dirty) {
      if (e.deleted) tree.push({ path: e.path, mode: '100644', type: 'blob', sha: null });
      else tree.push({ path: e.path, mode: '100644', type: 'blob', content: toMarkdown(e) });
    }
    // Images qui ne servent plus (remplacées ou projet supprimé).
    for (const path of originalFiles) {
      if (!live.has(path) && path.startsWith(`${dir}/src/assets/projects/`)) tree.push({ path, mode: '100644', type: 'blob', sha: null });
    }

    const names = dirty.map((e) => e.data.title).slice(0, 4).join(', ');
    const { sha: treeSha } = await gh('/git/trees', { base_tree: base.tree.sha, tree });
    const commit = await gh('/git/commits', {
      message: `Portfolio : modifications depuis l’éditeur (${names}${dirty.length > 4 ? '…' : ''})`,
      tree: treeSha,
      parents: [head],
    });
    await gh(`/git/refs/heads/${branch}`, { sha: commit.sha }, 'PATCH');

    expectedHead = commit.sha;
    originalFiles = live;
    uploads.clear();
    for (const e of dirty) {
      if (e.deleted) {
        entries.delete(e.data.slug);
        document.querySelectorAll(`article.project[data-slug="${e.data.slug}"]`).forEach((n) => n.remove());
      } else {
        e.isNew = false;
        e.original = JSON.stringify(e.data);
      }
    }
    if (pageSlug && !entries.has(pageSlug)) {
      leaving = true;
      location.href = BASE;
      return;
    }
    toast('Publié. Le site en ligne sera à jour d’ici une à deux minutes.', 'ok');
  } catch (err) {
    toast((err as Error).message, 'error');
  } finally {
    saving = false;
    updateBar();
  }
}

/* --------------------------------------------------------------------------
   Rendu : répercute les données sur la page
   -------------------------------------------------------------------------- */

function render(slug: string) {
  const e = entries.get(slug);
  if (!e) return;
  const d = e.data;
  document.querySelectorAll<HTMLElement>(`[data-slug="${slug}"]`).forEach((root) => {
    root.classList.toggle('st-deleted', !!e.deleted);
    root.querySelectorAll<HTMLElement>('[data-field="title"]').forEach((n) => {
      if (n !== document.activeElement && n.textContent !== d.title) n.textContent = d.title;
    });
    root.querySelectorAll<HTMLElement>('[data-field="meta"]').forEach((n) => (n.textContent = meta(d)));
    root.querySelectorAll('[data-field="thumbnail"]').forEach((n) => showPreview(n, d.thumbnail, d.thumbnailAlt));
  });
  if (slug === pageSlug) renderProjectPage();
  updateBar();
}

function renderProjectPage() {
  const e = entries.get(pageSlug!);
  if (!e || !projectPage) return;
  const d = e.data;

  // Fiche (disciplines, catégorie, contexte, année).
  const dl = projectPage.querySelector<HTMLElement>('[data-field="facts"]');
  if (dl) {
    const facts: [string, string | undefined][] = [
      ['Disciplines', d.disciplines.join(' · ')],
      ['Catégorie', d.categories.map(categoryLabel).join(', ')],
      ['Contexte', d.client],
      ['Année', d.year ? String(d.year) : undefined],
    ];
    dl.replaceChildren(...facts.filter(([, value]) => value).map(([label, value]) => {
      const row = scope(h('div'), dl);
      row.append(Object.assign(scope(h('dt'), dl), { textContent: label }), Object.assign(scope(h('dd'), dl), { textContent: value }));
      return row;
    }));
  }

  // Description courte : toujours présente en mode édition pour pouvoir l'écrire.
  let desc = projectPage.querySelector<HTMLElement>('[data-field="shortDescription"]');
  if (!desc && (editing || d.shortDescription)) {
    desc = scope(h('p', { class: 'project-page__desc', 'data-field': 'shortDescription' }), dl);
    dl?.after(desc);
  }
  if (desc) {
    if (desc !== document.activeElement) desc.textContent = d.shortDescription ?? '';
    desc.hidden = !editing && !d.shortDescription;
  }

  // Galerie : on garde les images d'origine et on ajoute les aperçus des nouvelles.
  const end = projectPage.querySelector('[data-gallery-end]')!;
  const old = [...projectPage.querySelectorAll<HTMLElement>('figure[data-image]')];
  const bySrc = new Map(old.map((f) => [f.dataset.src!, f]));
  const cover = projectPage.querySelector('[data-field="thumbnail"]');
  const figures = (d.images ?? []).map((img, i) => {
    const figure = bySrc.get(img.src) ?? scope(h('figure', { class: 'project-page__img', 'data-src': img.src }), cover);
    bySrc.delete(img.src);
    figure.dataset.image = String(i);
    showPreview(figure, img.src, img.alt);
    return figure;
  });
  bySrc.forEach((f) => f.remove());
  for (const f of figures) end.before(f);
  if (editing) decorate();
}

/* --------------------------------------------------------------------------
   Mode édition : zones modifiables et petits menus sur la page
   -------------------------------------------------------------------------- */

function editableText(node: HTMLElement, slug: string, field: 'title' | 'shortDescription', placeholder: string) {
  node.contentEditable = editing ? 'true' : 'false';
  node.classList.toggle('st-editable', editing);
  node.dataset.placeholder = placeholder;
  node.oninput = () => {
    const e = entries.get(slug)!;
    const value = (node.textContent ?? '').replace(/\s+/g, ' ').trim();
    if (field === 'shortDescription') e.data.shortDescription = value || undefined;
    else e.data.title = value;
    if (field === 'title') {
      document.querySelectorAll<HTMLElement>(`[data-slug="${slug}"] [data-field="title"]`).forEach((n) => {
        if (n !== node) n.textContent = value;
      });
    }
    updateBar();
  };
  node.onkeydown = (ev) => {
    if (ev.key === 'Enter' || ev.key === 'Escape') { ev.preventDefault(); node.blur(); }
  };
  node.onpaste = (ev) => {
    ev.preventDefault();
    document.execCommand('insertText', false, ev.clipboardData?.getData('text/plain') ?? '');
  };
}

function tools(parent: HTMLElement, ...buttons: HTMLElement[]) {
  parent.querySelector(':scope > .st-tools')?.remove();
  if (!editing) return;
  parent.classList.add('st-host');
  parent.append(h('div', { class: 'st-tools' }, ...buttons));
}

function decorate() {
  document.body.classList.toggle('st-editing', editing);

  // Accueil : vignettes des projets.
  document.querySelectorAll<HTMLElement>('article.project[data-slug]').forEach((card) => {
    const slug = card.dataset.slug!;
    const title = card.querySelector<HTMLElement>('[data-field="title"]');
    if (title) editableText(title, slug, 'title', 'Titre du projet');
    const e = entries.get(slug);
    if (e?.deleted && editing) {
      tools(card, button('Supprimé · Annuler', 'restore', 'st-btn--warn'));
      return;
    }
    tools(card,
      button('Modifier', 'edit'),
      button('Image', 'cover'),
      button('↑', 'up', 'st-btn--icon'),
      button('↓', 'down', 'st-btn--icon'),
      ...(e?.isNew ? [] : [button('Voir', 'open')]),
      button('Supprimer', 'delete', 'st-btn--danger'),
    );
  });

  // Page projet.
  if (projectPage && pageSlug) {
    const title = projectPage.querySelector<HTMLElement>('h1[data-field="title"]');
    if (title) editableText(title, pageSlug, 'title', 'Titre du projet');
    const desc = projectPage.querySelector<HTMLElement>('[data-field="shortDescription"]');
    if (desc) {
      editableText(desc, pageSlug, 'shortDescription', 'Ajouter une courte description…');
      desc.hidden = !editing && !entries.get(pageSlug)?.data.shortDescription;
    }
    const facts = projectPage.querySelector<HTMLElement>('[data-field="facts"]');
    if (facts) tools(facts, button('Modifier les infos', 'edit'));
    const cover = projectPage.querySelector<HTMLElement>('[data-field="thumbnail"]');
    if (cover) tools(cover, button('Changer l’image principale', 'cover'));
    projectPage.querySelectorAll<HTMLElement>('figure[data-image]').forEach((f) =>
      tools(f, button('Remplacer', 'img-replace'), button('↑', 'img-up', 'st-btn--icon'), button('↓', 'img-down', 'st-btn--icon'), button('Supprimer', 'img-delete', 'st-btn--danger')),
    );
    projectPage.querySelector('.st-add-images')?.remove();
    if (editing) {
      projectPage.querySelector('[data-gallery-end]')!.before(
        h('div', { class: 'st-add-images' }, button('+ Ajouter des images au projet', 'img-add', 'st-btn--big')),
      );
    }
  }
}

/* --------------------------------------------------------------------------
   Actions
   -------------------------------------------------------------------------- */

/** Réordonne : place le projet avant/après son voisin dans la grille, puis renumérote. */
function move(card: HTMLElement, dir: -1 | 1) {
  const neighbor = (dir < 0 ? card.previousElementSibling : card.nextElementSibling) as HTMLElement | null;
  if (!neighbor?.dataset.slug) return;
  const order = [...entries.values()]
    .filter((e) => !e.deleted)
    .sort((a, b) => (a.data.featuredOrder ?? 999) - (b.data.featuredOrder ?? 999))
    .map((e) => e.data.slug);
  const slug = card.dataset.slug!;
  order.splice(order.indexOf(slug), 1);
  order.splice(order.indexOf(neighbor.dataset.slug) + (dir > 0 ? 1 : 0), 0, slug);
  order.forEach((s, i) => (entries.get(s)!.data.featuredOrder = i + 1));
  // Réordonne toutes les grilles de l'accueil.
  document.querySelectorAll('.work__grid').forEach((grid) => {
    const cards = [...grid.querySelectorAll<HTMLElement>(':scope > article.project')];
    cards.sort((a, b) => order.indexOf(a.dataset.slug!) - order.indexOf(b.dataset.slug!)).forEach((c) => grid.append(c));
  });
  updateBar();
}

async function replaceCover(slug: string) {
  const [file] = await pickFiles();
  if (!file) return;
  const e = entries.get(slug)!;
  e.data.thumbnail = await addImage(slug, file, 'cover');
  render(slug);
}

function deleteProject(slug: string) {
  const e = entries.get(slug)!;
  if (!confirm(`Supprimer le projet « ${e.data.title} » ?\nIl disparaîtra du site après « Enregistrer ».`)) return;
  e.deleted = true;
  render(slug);
  decorate();
  if (slug === pageSlug) toast('Projet marqué pour suppression. Cliquez « Enregistrer » pour confirmer.');
}

async function galleryAction(action: string, figure: HTMLElement) {
  const e = entries.get(pageSlug!)!;
  const images = (e.data.images ??= []);
  const i = Number(figure.dataset.image);
  if (action === 'img-delete') {
    if (!confirm('Retirer cette image du projet ?')) return;
    images.splice(i, 1);
  } else if (action === 'img-up' || action === 'img-down') {
    const j = i + (action === 'img-up' ? -1 : 1);
    if (j < 0 || j >= images.length) return;
    [images[i], images[j]] = [images[j], images[i]];
  } else if (action === 'img-replace') {
    const [file] = await pickFiles();
    if (!file) return;
    images[i] = { ...images[i], src: await addImage(pageSlug!, file, 'image') };
  }
  render(pageSlug!);
}

async function addGalleryImages() {
  const files = await pickFiles(true);
  if (!files.length) return;
  const e = entries.get(pageSlug!)!;
  const images = (e.data.images ??= []);
  for (const file of files) {
    images.push({ src: await addImage(pageSlug!, file, 'image'), alt: `${e.data.title} — image ${images.length + 1}` });
  }
  render(pageSlug!);
}

document.addEventListener('click', (ev) => {
  const target = ev.target as HTMLElement;
  if (target.closest('.st-bar, .st-panel')) return;
  const btn = target.closest<HTMLElement>('[data-st]');
  const host = target.closest<HTMLElement>('[data-slug]');

  if (btn && host) {
    ev.preventDefault();
    ev.stopPropagation();
    const slug = host.dataset.slug!;
    const card = target.closest<HTMLElement>('article.project');
    const figure = target.closest<HTMLElement>('figure[data-image]');
    switch (btn.dataset.st) {
      case 'edit': return openPanel(slug);
      case 'cover': return void replaceCover(slug);
      case 'up': return card && move(card, -1);
      case 'down': return card && move(card, 1);
      case 'open': return void (location.href = card!.querySelector('a')!.href);
      case 'delete': return deleteProject(slug);
      case 'restore': entries.get(slug)!.deleted = false; render(slug); return decorate();
      case 'img-add': return void addGalleryImages();
      default: if (figure) return void galleryAction(btn.dataset.st!, figure);
    }
    return;
  }

  // En mode édition, les vignettes ne naviguent pas : un clic sur l'image la remplace.
  if (editing && target.closest('article.project a')) {
    ev.preventDefault();
    const card = target.closest<HTMLElement>('article.project')!;
    if (target.closest('[data-field="thumbnail"]') && !entries.get(card.dataset.slug!)?.deleted) void replaceCover(card.dataset.slug!);
  }
}, true);

/* --------------------------------------------------------------------------
   Panneau latéral : infos d'un projet (ou nouveau projet)
   -------------------------------------------------------------------------- */

function openPanel(slug?: string) {
  document.querySelector('.st-panel')?.remove();
  const e = slug ? entries.get(slug)! : null;
  const d: Partial<Data> = e?.data ?? { featured: true, categories: [activeCategory()], disciplines: [] };
  let coverFile: File | null = null;

  const field = (label: string, input: HTMLElement, hint = '') =>
    h('label', { class: 'st-field' }, h('span', {}, label), input, ...(hint ? [h('small', {}, hint)] : []));
  const input = (name: string, value = '', type = 'text') => h('input', { name, type, value: String(value) });

  const title = input('title', d.title);
  const slugInput = input('slug', d.slug ?? '');
  let slugTouched = false;
  slugInput.addEventListener('input', () => (slugTouched = true));
  title.addEventListener('input', () => { if (!e && !slugTouched) slugInput.value = slugify(title.value); });

  const cats = h('div', { class: 'st-checks' }, ...payload.categories.map((c) => {
    const box = h('input', { type: 'checkbox', name: 'categories', value: c.id });
    box.checked = !!d.categories?.includes(c.id);
    return h('label', {}, box, ` ${c.label}`);
  }));
  const featured = h('input', { type: 'checkbox', name: 'featured' });
  featured.checked = d.featured ?? false;
  const placeholder = h('input', { type: 'checkbox', name: 'placeholder' });
  placeholder.checked = d.placeholder ?? false;
  const desc = h('textarea', { name: 'shortDescription', rows: '4' });
  desc.value = d.shortDescription ?? '';

  const coverName = h('span', { class: 'st-file' }, e ? 'Image actuelle conservée' : 'Aucune image choisie');
  const coverBtn = button(e ? 'Changer l’image' : 'Choisir l’image', 'pick');
  coverBtn.addEventListener('click', async () => {
    const [file] = await pickFiles();
    if (file) { coverFile = file; coverName.textContent = file.name; }
  });

  const form = h('form', { class: 'st-panel__form' },
    field('Titre', title),
    ...(e ? [] : [field('Adresse de la page', slugInput, 'Minuscules, chiffres et tirets. Ne pourra plus changer.')]),
    h('fieldset', { class: 'st-field' }, h('legend', {}, 'Catégories'), cats),
    field('Disciplines', input('disciplines', (d.disciplines ?? []).join(', ')), 'Séparées par des virgules, ex. : Illustration, Design de collection'),
    field('Contexte / client', input('client', d.client ?? '')),
    field('Année', input('year', d.year ? String(d.year) : '', 'number')),
    field('Description courte', desc),
    h('div', { class: 'st-field' }, h('span', {}, 'Image principale'), h('div', { class: 'st-row' }, coverBtn, coverName)),
    field('Description de l’image', input('thumbnailAlt', d.thumbnailAlt ?? ''), 'Pour les personnes malvoyantes et le référencement.'),
    h('label', { class: 'st-check' }, featured, ' Afficher sur l’accueil'),
    h('label', { class: 'st-check' }, placeholder, ' Contenu provisoire'),
    h('div', { class: 'st-row st-panel__actions' },
      h('button', { type: 'submit', class: 'st-btn st-btn--primary' }, e ? 'Appliquer' : 'Créer le projet'),
      h('button', { type: 'button', class: 'st-btn', 'data-close': '' }, 'Fermer'),
    ),
  );

  const panel = h('aside', { class: 'st-panel', 'aria-label': 'Infos du projet' },
    h('header', { class: 'st-panel__head' }, h('strong', {}, e ? `Infos · ${e.data.title}` : 'Nouveau projet'), h('button', { type: 'button', class: 'st-btn st-btn--icon', 'data-close': '', 'aria-label': 'Fermer' }, '×')),
    form,
  );
  panel.querySelectorAll('[data-close]').forEach((b) => b.addEventListener('click', () => panel.remove()));

  form.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const fd = new FormData(form);
    const str = (k: string) => String(fd.get(k) ?? '').trim();
    const next: Data = {
      ...(e?.data ?? ({} as Data)),
      title: str('title'),
      slug: e ? e.data.slug : slugify(slugInput.value),
      categories: fd.getAll('categories').map(String),
      disciplines: str('disciplines').split(',').map((s) => s.trim()).filter(Boolean),
      client: str('client') || undefined,
      year: str('year') ? Number(str('year')) : undefined,
      shortDescription: str('shortDescription') || undefined,
      thumbnailAlt: str('thumbnailAlt') || str('title'),
      featured: featured.checked,
      placeholder: placeholder.checked || undefined,
      thumbnail: e?.data.thumbnail ?? '',
    };
    const problem = !next.title ? 'Donnez un titre au projet.'
      : !next.categories.length ? 'Choisissez au moins une catégorie.'
      : !next.disciplines.length ? 'Indiquez au moins une discipline.'
      : !e && !/^[a-z0-9-]+$/.test(next.slug) ? 'L’adresse de la page est invalide.'
      : !e && entries.has(next.slug) ? 'Un projet utilise déjà cette adresse.'
      : !e && !coverFile ? 'Choisissez une image principale.' : null;
    if (problem) return toast(problem, 'error');

    if (coverFile) next.thumbnail = await addImage(next.slug, coverFile, 'cover');
    if (e) {
      e.data = next;
    } else {
      next.featuredOrder = Math.max(0, ...[...entries.values()].map((x) => x.data.featuredOrder ?? 0)) + 1;
      entries.set(next.slug, {
        path: `${payload.repo.dir}/src/content/projects/${next.slug}.md`,
        body: '',
        data: next,
        original: '',
        isNew: true,
      });
      insertCards(next);
    }
    panel.remove();
    render(next.slug);
    decorate();
    toast(e ? 'Modifications appliquées. Pensez à enregistrer.' : 'Projet ajouté. Pensez à enregistrer.');
  });

  document.body.append(panel);
  (title as HTMLInputElement).focus();
}

function activeCategory() {
  return document.querySelector<HTMLElement>('.work__panel.is-active')?.dataset.panel ?? payload.categories[0].id;
}

/** Aperçu d'un nouveau projet dans les grilles de l'accueil, avant publication. */
function insertCards(d: Data) {
  const template = document.querySelector<HTMLElement>('article.project');
  if (!isHome || !template || !d.featured) {
    toast('Le projet apparaîtra sur l’accueil une fois enregistré et publié.');
    return;
  }
  document.querySelectorAll<HTMLElement>('[data-panel]').forEach((panel) => {
    if (!d.categories.includes(panel.dataset.panel!)) return;
    const card = template.cloneNode(true) as HTMLElement;
    card.querySelector('.st-tools')?.remove();
    card.className = card.className.replace(/\bl-\w+/, 'l-medium').replace(/\bst-deleted\b/, '');
    card.dataset.slug = d.slug;
    card.querySelector<HTMLElement>('.project__index')!.textContent = '+';
    panel.querySelector('.work__grid')!.append(card);
  });
}

/* --------------------------------------------------------------------------
   Barre d'édition flottante (déplaçable)
   -------------------------------------------------------------------------- */

const bar = h('div', { class: 'st-bar', role: 'toolbar', 'aria-label': 'Menu d’édition' });

function buildBar() {
  const grip = h('span', { class: 'st-bar__grip', title: 'Déplacer le menu', 'aria-hidden': 'true' }, '⠿');
  bar.append(
    grip,
    h('span', { class: 'st-bar__brand' }, 'Admin'),
    button('', 'mode', 'st-bar__mode'),
    button('+ Projet', 'new'),
    ...(pageSlug ? [button('Infos', 'info'), button('Supprimer le projet', 'delete-page', 'st-btn--danger')] : []),
    button('Enregistrer', 'save', 'st-btn--primary st-bar__save'),
    button('Annuler', 'discard'),
    button('Quitter', 'exit'),
  );
  document.body.append(bar);

  bar.addEventListener('click', (ev) => {
    const action = (ev.target as HTMLElement).closest<HTMLElement>('[data-st]')?.dataset.st;
    switch (action) {
      case 'mode':
        editing = !editing;
        sessionStorage.setItem('st-admin-mode', editing ? 'edit' : 'preview');
        document.querySelector('.st-panel')?.remove();
        if (pageSlug) renderProjectPage();
        decorate();
        return updateBar();
      case 'new': return openPanel();
      case 'info': return openPanel(pageSlug);
      case 'delete-page': return deleteProject(pageSlug!);
      case 'save': return void save();
      case 'discard':
        if (!dirtyEntries().length || confirm('Annuler toutes les modifications non enregistrées ?')) { leaving = true; location.reload(); }
        return;
      case 'exit':
        if (dirtyEntries().length && !confirm('Des modifications ne sont pas enregistrées. Quitter quand même ?')) return;
        leaving = true;
        endSession();
        location.reload();
    }
  });

  // Déplacement à la souris ou au doigt ; la position est mémorisée pendant la session.
  const place = (x: number, y: number) => {
    const r = bar.getBoundingClientRect();
    x = Math.min(Math.max(8, x), innerWidth - r.width - 8);
    y = Math.min(Math.max(8, y), innerHeight - r.height - 8);
    Object.assign(bar.style, { left: `${x}px`, top: `${y}px`, bottom: 'auto', transform: 'none' });
    return { x, y };
  };
  try {
    const saved = JSON.parse(sessionStorage.getItem('st-admin-bar') ?? 'null');
    if (saved) requestAnimationFrame(() => place(saved.x, saved.y));
  } catch { /* position par défaut */ }
  grip.addEventListener('pointerdown', (ev) => {
    ev.preventDefault();
    const r = bar.getBoundingClientRect();
    const dx = ev.clientX - r.left;
    const dy = ev.clientY - r.top;
    grip.setPointerCapture(ev.pointerId);
    const onMove = (m: PointerEvent) => sessionStorage.setItem('st-admin-bar', JSON.stringify(place(m.clientX - dx, m.clientY - dy)));
    grip.addEventListener('pointermove', onMove);
    grip.addEventListener('pointerup', () => grip.removeEventListener('pointermove', onMove), { once: true });
  });
}

function updateBar() {
  const count = dirtyEntries().length;
  const save = bar.querySelector<HTMLButtonElement>('.st-bar__save');
  if (!save) return;
  save.textContent = saving ? 'Enregistrement…' : count ? `Enregistrer (${count})` : 'Enregistrer';
  save.disabled = saving || !count || stale;
  bar.querySelector('.st-bar__mode')!.textContent = editing ? 'Aperçu' : 'Modifier';
  bar.classList.toggle('is-preview', !editing);
}

addEventListener('beforeunload', (ev) => {
  if (!leaving && dirtyEntries().length) ev.preventDefault();
});

/* --------------------------------------------------------------------------
   Démarrage
   -------------------------------------------------------------------------- */

async function start() {
  buildBar();
  try {
    payload = await (await fetch(`${BASE}admin/data.json`, { cache: 'no-store' })).json();
  } catch {
    return toast('Impossible de charger les données de l’éditeur.', 'error');
  }
  for (const p of payload.projects) {
    entries.set(p.data.slug, { path: p.path, body: p.body, data: p.data, original: JSON.stringify(p.data) });
    filesOf(p.data).forEach((f) => originalFiles.add(f));
  }
  // Relie les images de la galerie à leur chemin, pour pouvoir les réordonner.
  if (pageSlug) {
    const images = entries.get(pageSlug)?.data.images ?? [];
    projectPage!.querySelectorAll<HTMLElement>('figure[data-image]').forEach((f) => (f.dataset.src = images[Number(f.dataset.image)]?.src ?? ''));
  }

  expectedHead = payload.buildSha;
  if (expectedHead) {
    headSha().then((head) => {
      if (head === expectedHead) return;
      stale = true;
      updateBar();
      bar.after(h('div', { class: 'st-banner' }, 'Une publication récente n’est pas encore en ligne. Rechargez la page dans une minute avant de modifier.'));
    }).catch((err) => toast((err as Error).message, 'error'));
  }

  if (pageSlug) renderProjectPage();
  decorate();
  updateBar();
}

if (token) void start();
else location.href = ADMIN_URL;
