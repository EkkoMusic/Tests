// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

// URL publique du site. À adapter au domaine final (ex. https://sarahtamisier.com
// avec BASE_PATH=/). Les valeurs par défaut correspondent à GitHub Pages.
const site = process.env.SITE_URL ?? 'https://ekkomusic.github.io';
const base = process.env.BASE_PATH ?? '/Tests/sarah-tamisier';

export default defineConfig({
  site,
  base,
  trailingSlash: 'always',
  integrations: [
    sitemap({
      // Pages provisoires exclues du sitemap tant qu'elles ne sont pas finalisées.
      filter: (page) => !page.includes('/a-propos/') && !page.includes('/admin/'),
    }),
  ],
  image: {
    // Qualité élevée : ce sont des illustrations.
    service: { entrypoint: 'astro/assets/services/sharp', config: { jpeg: { quality: 85 }, webp: { quality: 85 }, avif: { quality: 70 } } },
  },
});
