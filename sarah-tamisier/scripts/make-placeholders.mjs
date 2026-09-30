// Génère des visuels de remplacement (un par projet) tant que les vraies images
// ne sont pas disponibles. Usage : npm run placeholders
// Chaque fichier sera remplacé par un vrai visuel au même chemin (ou le chemin
// sera changé dans le frontmatter du projet).
import sharp from 'sharp';
import { mkdir } from 'node:fs/promises';

const W = 2400;
const items = [
  // slug, ratio (w/h), fond, forme, titre
  ['temple-perdu', 16 / 9, '#2f3a33', '#8a9a7b', 'Le Temple perdu'],
  ['rencontre-liminale', 3 / 2, '#3b3847', '#a59bb8', 'Rencontre liminale'],
  ['dragon-ecureuil', 3 / 4, '#5a3b2a', '#d49a63', 'Le Dragon-écureuil'],
  ['course-poursuite-maebi', 16 / 10, '#243442', '#7fa3b8', 'Course poursuite — Maebi'],
  ['papinou-et-nora', 3 / 2, '#4a4030', '#c9b27a', 'Papinou & Nora'],
  ['bigoudene-70s', 4 / 5, '#e8d9c4', '#b8563a', 'Bigoudène 70’s'],
  ['calypso', 1, '#d7e2de', '#3f7f86', 'Calypso'],
  ['alice-et-les-pitchounes', 4 / 5, '#f0dcd6', '#c2677a', 'Alice & les Pitchounes'],
  ['bolipop', 1, '#efe6c8', '#d08a2e', 'Bolipop'],
];

for (const [slug, ratio, bg, fg, title] of items) {
  const H = Math.round(W / ratio);
  const light = parseInt(bg.slice(1, 3), 16) > 160;
  const ink = light ? '#1a1714' : '#f3efe7';
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}">
    <rect width="100%" height="100%" fill="${bg}"/>
    <circle cx="${W * 0.68}" cy="${H * 0.46}" r="${Math.min(W, H) * 0.28}" fill="${fg}" opacity=".85"/>
    <rect x="${W * 0.12}" y="${H * 0.58}" width="${W * 0.36}" height="${H * 0.22}" fill="${fg}" opacity=".45"/>
    <text x="${W * 0.06}" y="${H * 0.12}" font-family="DejaVu Sans, sans-serif" font-size="${W * 0.018}" letter-spacing="6" fill="${ink}" opacity=".7">PLACEHOLDER</text>
    <text x="${W * 0.06}" y="${H * 0.92}" font-family="DejaVu Serif, serif" font-size="${W * 0.04}" fill="${ink}">${title.replace(/&/g, "&amp;")}</text>
  </svg>`;
  await mkdir(`src/assets/projects/${slug}`, { recursive: true });
  await sharp(Buffer.from(svg)).jpeg({ quality: 82, mozjpeg: true }).toFile(`src/assets/projects/${slug}/cover.jpg`);
}

// Image Open Graph par défaut (1200×630)
await sharp(Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630">
  <rect width="100%" height="100%" fill="#f3efe7"/>
  <text x="80" y="330" font-family="DejaVu Serif, serif" font-size="88" fill="#1a1714">Sarah Tamisier</text>
  <text x="84" y="400" font-family="DejaVu Sans, sans-serif" font-size="26" letter-spacing="4" fill="#5f5850">ILLUSTRATION · CONCEPT ART · DESIGN</text>
</svg>`)).jpeg({ quality: 85 }).toFile('public/og-default.jpg');

console.log(`${items.length} placeholders + og-default.jpg générés.`);
