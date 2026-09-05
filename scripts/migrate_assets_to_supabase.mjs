#!/usr/bin/env node

import { createHash } from "node:crypto";
import { promises as fs } from "node:fs";
import path from "node:path";

const ROOT = path.resolve(import.meta.dirname, "..");
const ENDPOINT = "https://yjdogvojaeerbedqjznz.supabase.co/functions/v1/travel-blog-admin";
const token = process.argv[2];

if (!token) {
  console.error("Usage: node migrate_assets_to_supabase.mjs <write-token>");
  process.exitCode = 2;
  process.exit();
}

const includeRoots = ["data", "docs", "site", "scripts"];
const allowedExtensions = new Set([".html", ".json", ".js", ".py"]);
const urlPattern = /https:\/\/(?:images|source)\.unsplash\.com\/[^\s"'<>)]*/g;

async function walk(directory) {
  const files = [];
  for (const entry of await fs.readdir(directory, { withFileTypes: true })) {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...await walk(fullPath));
    else if (allowedExtensions.has(path.extname(entry.name).toLowerCase())) files.push(fullPath);
  }
  return files;
}

async function callAdmin(body, attempts = 3) {
  let lastError;
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      const response = await fetch(ENDPOINT, {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "x-blog-write-token": token,
        },
        body: JSON.stringify(body),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(`${response.status} ${JSON.stringify(result)}`);
      return result;
    } catch (error) {
      lastError = error;
      if (attempt < attempts) await new Promise((resolve) => setTimeout(resolve, attempt * 1200));
    }
  }
  throw lastError;
}

async function runPool(items, worker, concurrency = 6) {
  let cursor = 0;
  const results = new Array(items.length);
  async function run() {
    while (cursor < items.length) {
      const index = cursor++;
      results[index] = await worker(items[index], index);
    }
  }
  await Promise.all(Array.from({ length: Math.min(concurrency, items.length) }, run));
  return results;
}

const files = (await Promise.all(includeRoots.map((root) => walk(path.join(ROOT, root))))).flat();
const fileContents = new Map();
const sourceUrls = new Set();

for (const file of files) {
  const content = await fs.readFile(file, "utf8");
  fileContents.set(file, content);
  for (const match of content.matchAll(urlPattern)) {
    sourceUrls.add(match[0].replaceAll("&amp;", "&"));
  }
}

const urls = [...sourceUrls].sort();
console.log(`Found ${urls.length} unique Unsplash image URLs.`);

const imported = await runPool(urls, async (sourceUrl, index) => {
  const result = await callAdmin({ action: "import_url", source_url: sourceUrl });
  if ((index + 1) % 25 === 0 || index + 1 === urls.length) {
    console.log(`Imported ${index + 1}/${urls.length}`);
  }
  return {
    source_url: sourceUrl,
    public_url: result.public_url,
    object_path: result.object_path,
    size_bytes: result.size_bytes,
    sha256: result.sha256,
  };
});

const mapping = new Map(imported.map((item) => [item.source_url, item.public_url]));
let changedFiles = 0;
for (const [file, original] of fileContents) {
  let updated = original;
  for (const [sourceUrl, publicUrl] of mapping) {
    updated = updated.replaceAll(sourceUrl, publicUrl);
    updated = updated.replaceAll(sourceUrl.replaceAll("&", "&amp;"), publicUrl);
  }
  if (updated !== original) {
    await fs.writeFile(file, updated, "utf8");
    changedFiles += 1;
  }
}

const reportDir = path.join(ROOT, ".migration");
await fs.mkdir(reportDir, { recursive: true });
const report = {
  generated_at: new Date().toISOString(),
  endpoint: ENDPOINT,
  source_count: imported.length,
  changed_file_count: changedFiles,
  total_size_bytes: imported.reduce((sum, item) => sum + Number(item.size_bytes || 0), 0),
  mapping_sha256: createHash("sha256").update(JSON.stringify(imported)).digest("hex"),
  items: imported,
};
await fs.writeFile(path.join(reportDir, "media-map.json"), JSON.stringify(report, null, 2) + "\n", "utf8");
console.log(`Rewrote ${changedFiles} files and saved .migration/media-map.json.`);
