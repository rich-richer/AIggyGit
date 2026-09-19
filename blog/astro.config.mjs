import { defineConfig } from 'astro/config';

export default defineConfig({
  output: 'static',
  trailingSlash: 'never',
  markdown: {
    shikiConfig: { theme: 'min-light' },
  },
});
