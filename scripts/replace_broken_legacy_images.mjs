#!/usr/bin/env node

import { promises as fs } from "node:fs";
import path from "node:path";

const ROOT = path.resolve(import.meta.dirname, "..");
const POSTS_DIR = path.join(ROOT, "docs", "posts");
const sourcePattern = /https:\/\/source\.unsplash\.com\/[^\s"'<>)]*/g;
const supabasePattern = /https:\/\/yjdogvojaeerbedqjznz\.supabase\.co\/storage\/v1\/object\/public\/travel-blog-media\/[^\s"'<>)]*/g;

const files = (await fs.readdir(POSTS_DIR)).filter((name) => name.endsWith(".html"));
const coverBySlug = new Map();
let replacementCount = 0;

for (const name of files) {
  const file = path.join(POSTS_DIR, name);
  const original = await fs.readFile(file, "utf8");
  const internalImages = original.match(supabasePattern) || [];
  if (!internalImages.length) continue;
  const fallback = internalImages[0];
  const legacyImages = original.match(sourcePattern) || [];
  let updated = original;
  for (const legacy of legacyImages) {
    updated = updated.replaceAll(legacy, fallback);
    replacementCount += 1;
  }
  if (updated !== original) await fs.writeFile(file, updated, "utf8");
  coverBySlug.set(name.replace(/\.html$/, ""), fallback);
}

for (const relative of [path.join("data", "posts.json"), path.join("docs", "data", "posts.json")]) {
  const file = path.join(ROOT, relative);
  const posts = JSON.parse(await fs.readFile(file, "utf8"));
  for (const post of posts) {
    if (String(post.cover_image || "").startsWith("https://source.unsplash.com/")) {
      const fallback = coverBySlug.get(post.slug);
      if (!fallback) throw new Error(`No Supabase fallback image for ${post.slug}`);
      post.cover_image = fallback;
      replacementCount += 1;
    }
  }
  await fs.writeFile(file, JSON.stringify(posts, null, 2) + "\n", "utf8");
}

console.log(`Replaced ${replacementCount} unavailable legacy image references with migrated Supabase images.`);
