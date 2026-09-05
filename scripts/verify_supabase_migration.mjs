#!/usr/bin/env node

import { promises as fs } from 'node:fs';
import path from 'node:path';

const ROOT = path.resolve(import.meta.dirname, '..');
const POST_DIR = path.join(ROOT, 'docs', 'posts');
const SUPABASE_MEDIA_PREFIX = 'https://yjdogvojaeerbedqjznz.supabase.co/storage/v1/object/public/travel-blog-media/';
const failures = [];

for (const relative of [
  'data/posts.json',
  'data/history.json',
  'data/week_plan.json',
  'data/locations.json',
  'data/site_theme.json',
  'docs/data/posts.json',
  'docs/data/site_theme.json'
]) {
  try {
    await fs.access(path.join(ROOT, relative));
    failures.push(relative + ' should not remain in GitHub');
  } catch {}
}

const postFiles = (await fs.readdir(POST_DIR)).filter((name) => name.endsWith('.html'));
let imageCount = 0;
for (const name of postFiles) {
  const content = await fs.readFile(path.join(POST_DIR, name), 'utf8');
  if (!content.includes('../assets/js/supabase-config.js') || !content.includes('../assets/js/supabase-data.js')) {
    failures.push(name + ' is missing Supabase data scripts');
  }
  const imageUrls = [...content.matchAll(/<img[^>]+src=["']([^"']+)["']/gi)].map((match) => match[1]);
  imageCount += imageUrls.length;
  for (const url of imageUrls) {
    if (!url.startsWith(SUPABASE_MEDIA_PREFIX)) {
      failures.push(name + ' has non-Supabase image: ' + url);
    }
  }
}

for (const relative of ['docs/index.html', 'site/index.html']) {
  const content = await fs.readFile(path.join(ROOT, relative), 'utf8');
  if (!content.includes('supabase-config.js') || !content.includes('supabase-data.js')) {
    failures.push(relative + ' is not connected to Supabase');
  }
  if (/fetch\(['"]data\//.test(content)) failures.push(relative + ' still reads local JSON');
}

const workflow = await fs.readFile(path.join(ROOT, '.github', 'workflows', 'daily-post.yml'), 'utf8');
if (!workflow.includes('TRAVEL_BLOG_WRITE_TOKEN')) failures.push('daily workflow is missing protected Supabase access');
if (/git add[^\n]*data\//.test(workflow)) failures.push('daily workflow still commits data JSON');

if (failures.length) {
  console.error(failures.join('\n'));
  process.exitCode = 1;
} else {
  console.log(JSON.stringify({ ok:true, post_pages:postFiles.length, verified_image_references:imageCount }));
}
