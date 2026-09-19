import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const posts = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/posts' }),
  schema: z.object({
    title: z.string(),
    titleEn: z.string().optional(),
    description: z.string(),
    descriptionEn: z.string().optional(),
    date: z.coerce.date(),
    lang: z.enum(['zh', 'en']).default('zh'),
    tags: z.array(z.string()).default([]),
    draft: z.boolean().default(false),
    sourceTitle: z.string().optional(),
    sourceUrl: z.string().url().optional(),
  }),
});

export const collections = { posts };
