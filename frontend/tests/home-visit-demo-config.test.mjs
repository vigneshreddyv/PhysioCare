import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';

const repoRoot = path.resolve(import.meta.dirname, '..', '..');
const launcher = fs.readFileSync(
  path.join(repoRoot, 'backend', 'scripts', 'HomeVisitDemo.ps1'),
  'utf8',
);
const viteConfig = fs.readFileSync(
  path.join(repoRoot, 'frontend', 'vite.config.js'),
  'utf8',
);
const apiClient = fs.readFileSync(
  path.join(repoRoot, 'frontend', 'src', 'services', 'api.js'),
  'utf8',
);
const homeVisitEnv = fs.readFileSync(
  path.join(repoRoot, 'frontend', '.env.home-visit-demo'),
  'utf8',
);

test('Home Visit launcher binds Vite to the strict dedicated port', () => {
  assert.match(launcher, /function Resolve-NpmCommand/);
  assert.match(launcher, /Get-Command npm\.cmd -CommandType Application/);
  assert.match(launcher, /\$npmCandidates = @\(/);
  assert.match(launcher, /Get-Command node\.exe -CommandType Application/);
  assert.match(launcher, /Split-Path -Parent \(\[string\]\$activeNode\[0\]\.Source\)/);
  assert.match(launcher, /\$selectedPath = \[string\]\$npmCandidates\[0\]/);
  assert.match(launcher, /return \[string\]\$selectedPath/);
  assert.match(launcher, /selected Windows npm command wrapper is invalid/);
  assert.match(launcher, /\$npmCommand = Resolve-NpmCommand/);
  assert.match(launcher, /Start-ManagedProcess "frontend" \$npmCommand/);
  assert.match(launcher, /Start-Process -FilePath \$FilePath -ArgumentList \$Arguments -WorkingDirectory \$WorkingDirectory/);
  assert.match(launcher, /-PassThru/);
  assert.match(launcher, /Write-TrackedProcess \$Role \$process\.Id/);
  assert.match(
    launcher,
    /"run", "dev", "--", "--mode", "home-visit-demo", "--host", "127\.0\.0\.1", "--port", "\$FrontendPort", "--strictPort"/,
  );
  assert.match(launcher, /\$FrontendPort = 5176/);
});

test('process tracking keeps zero, one, and multiple records as arrays', () => {
  assert.match(
    launcher,
    /\$tracked = @\(@\(Read-TrackedProcesses\) \| Where-Object \{ \$_.role -ne \$Role \}\)/g,
  );
  assert.match(launcher, /Failed to register the \$Role process in the tracking file/);
  assert.match(launcher, /\$tracked \+= \[PSCustomObject\]@\{ role = \$Role; pid = \$ProcessId \}/);
});

test('Vite uses the isolated proxy only in Home Visit Demo mode', () => {
  assert.match(viteConfig, /mode === 'home-visit-demo'/);
  assert.match(
    viteConfig,
    /isHomeVisitDemo\s*\?\s*'http:\/\/127\.0\.0\.1:8002'\s*:\s*'http:\/\/127\.0\.0\.1:8000'/s,
  );
  assert.match(viteConfig, /strictPort: isHomeVisitDemo/);
  assert.doesNotMatch(
    viteConfig.replace(/isHomeVisitDemo\s*\?\s*'http:\/\/127\.0\.0\.1:8002'\s*:\s*'http:\/\/127\.0\.0\.1:8000'/s, ''),
    /127\.0\.0\.1:800[01]/,
  );
});

test('Home Visit API configuration selects port 8002 without another fallback', () => {
  assert.match(homeVisitEnv, /^VITE_API_URL=http:\/\/127\.0\.0\.1:8002\/api$/m);
  assert.match(apiClient, /import\.meta\.env\.VITE_API_URL/);
  assert.doesNotMatch(apiClient, /127\.0\.0\.1:800[01]/);
});
