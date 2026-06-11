// sync-data.mjs — snapshot the three precomputed Helm artifacts from the
// (gitignored) repo-root data_cache/ into dashboard/public/data so the static
// export is fully self-contained and the demo runs without regenerating data.
//
// Run automatically via the `predev` / `prebuild` npm hooks, or manually:
//   node scripts/sync-data.mjs
//
// The snapshot copies under public/data ARE committed (they are small).

import { copyFileSync, existsSync, mkdirSync, statSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(__dirname, '..', '..');
const srcDir = join(repoRoot, 'data_cache');
const destDir = resolve(__dirname, '..', 'public', 'data');

const ARTIFACTS = [
  'regime_artifact.json',
  'onchain_validation_artifact.json',
  'validation_artifact.json',
];

mkdirSync(destDir, { recursive: true });

let copied = 0;
let kept = 0;
for (const name of ARTIFACTS) {
  const src = join(srcDir, name);
  const dest = join(destDir, name);
  if (existsSync(src)) {
    copyFileSync(src, dest);
    const kb = (statSync(dest).size / 1024).toFixed(1);
    console.log(`  ✓ synced ${name} (${kb} kB)`);
    copied += 1;
  } else if (existsSync(dest)) {
    // Source missing (e.g. CI without data_cache) but a committed snapshot
    // already exists — keep it so the build still succeeds.
    console.log(`  • kept committed snapshot ${name} (source not found)`);
    kept += 1;
  } else {
    console.warn(`  ✗ MISSING ${name} — not in data_cache/ nor public/data/`);
  }
}

console.log(`sync-data: ${copied} copied, ${kept} kept from snapshot.`);
