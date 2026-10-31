import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';


const source = async (relativePath) => readFile(new URL(relativePath, import.meta.url), 'utf8');


test('CI enforces bounded JavaScript and CSS production assets', async () => {
  const [packageSource, budgetSource, ciSource] = await Promise.all([
    source('../package.json'),
    source('../scripts/check-bundle-budget.mjs'),
    source('../../.github/workflows/ci.yml'),
  ]);
  const packageJson = JSON.parse(packageSource);

  assert.equal(packageJson.scripts['check:bundle'], 'node scripts/check-bundle-budget.mjs');
  assert.match(budgetSource, /'\.js': 450 \* 1024/);
  assert.match(budgetSource, /'\.css': 300 \* 1024/);
  assert.match(budgetSource, /process\.exitCode = 1/);
  assert.match(ciSource, /Enforce production bundle budget[\s\S]*npm run check:bundle/);
});
