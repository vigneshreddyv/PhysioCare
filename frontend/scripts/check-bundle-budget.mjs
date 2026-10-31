import { readdir, stat } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

const assetsDirectory = fileURLToPath(new URL('../dist/assets/', import.meta.url));
const budgets = {
  '.js': 450 * 1024,
  '.css': 300 * 1024,
};

const formatKiB = (bytes) => `${(bytes / 1024).toFixed(1)} KiB`;
const assets = await readdir(assetsDirectory);
const measured = await Promise.all(
  assets
    .filter((name) => Object.keys(budgets).some((extension) => name.endsWith(extension)))
    .map(async (name) => ({
      name,
      bytes: (await stat(new URL(`../dist/assets/${name}`, import.meta.url))).size,
    })),
);

const violations = measured.filter(({ name, bytes }) => {
  const extension = name.endsWith('.css') ? '.css' : '.js';
  return bytes > budgets[extension];
});

if (violations.length > 0) {
  for (const { name, bytes } of violations) {
    const extension = name.endsWith('.css') ? '.css' : '.js';
    console.error(`${name}: ${formatKiB(bytes)} exceeds the ${formatKiB(budgets[extension])} ${extension} budget.`);
  }
  process.exitCode = 1;
} else {
  const largest = measured.sort((left, right) => right.bytes - left.bytes).slice(0, 3);
  console.log(`Bundle budget passed (${measured.length} JS/CSS assets checked).`);
  for (const { name, bytes } of largest) console.log(`  ${name}: ${formatKiB(bytes)}`);
}
