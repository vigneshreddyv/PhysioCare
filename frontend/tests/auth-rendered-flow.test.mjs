import assert from 'node:assert/strict';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { after, before, test } from 'node:test';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import react from '@vitejs/plugin-react';
import { createLogger, createServer } from 'vite';

const root = fileURLToPath(new URL('..', import.meta.url));
const originalSessionStorage = globalThis.sessionStorage;
let vite;
let cacheDir;
let AuthContext;
let AuthProvider;
let EmailLogin;
let RoleProtectedRoute;

before(async () => {
  cacheDir = await mkdtemp(join(tmpdir(), 'physiocare-auth-render-'));
  vite = await createServer({
    configFile: false,
    root,
    plugins: [react()],
    cacheDir,
    customLogger: createLogger('silent'),
    server: { middlewareMode: true, hmr: false },
    appType: 'custom',
  });
  [{ AuthContext, AuthProvider }, { default: EmailLogin }, { default: RoleProtectedRoute }] = await Promise.all([
    vite.ssrLoadModule('/src/context/AuthContext.jsx'),
    vite.ssrLoadModule('/src/pages/common/EmailLogin.jsx'),
    vite.ssrLoadModule('/src/routes/RoleProtectedRoute.jsx'),
  ]);
});

after(async () => {
  await vite?.close();
  if (cacheDir) await rm(cacheDir, { recursive: true, force: true });
  if (originalSessionStorage === undefined) delete globalThis.sessionStorage;
  else globalThis.sessionStorage = originalSessionStorage;
});

function renderLogin(pendingLogin) {
  return renderToStaticMarkup(React.createElement(
    AuthContext.Provider,
    { value: { login: async () => true, retryPendingLogin: async () => true, pendingLogin } },
    React.createElement(MemoryRouter, null, React.createElement(EmailLogin)),
  ));
}

function renderGuard({ user, loading = false }) {
  return renderToStaticMarkup(React.createElement(
    AuthContext.Provider,
    { value: { user, loading, isAuthenticated: Boolean(user) } },
    React.createElement(MemoryRouter, null,
      React.createElement(RoleProtectedRoute, { allowedRoles: ['patient'] },
        React.createElement('p', null, 'Sensitive fictional patient content'),
      ),
    ),
  ));
}

test('unconfirmed server logout hides patient content and displays a retry', () => {
  globalThis.sessionStorage = { getItem: () => '1', setItem() {}, removeItem() {} };
  const html = renderToStaticMarkup(React.createElement(
    QueryClientProvider,
    { client: new QueryClient() },
    React.createElement(AuthProvider, null,
      React.createElement('p', null, 'Sensitive fictional patient content'),
    ),
  ));

  assert.match(html, /role="alert"/);
  assert.match(html, /Sign-out could not be confirmed/);
  assert.match(html, /server may still have an active session/);
  assert.match(html, /Retry sign-out/);
  assert.doesNotMatch(html, /Sensitive fictional patient content/);
});

test('unreadable session storage renders a private, recoverable sign-out state', () => {
  globalThis.sessionStorage = {
    getItem: () => { throw new Error('storage unavailable'); },
    setItem() {},
    removeItem() {},
  };
  const html = renderToStaticMarkup(React.createElement(
    QueryClientProvider,
    { client: new QueryClient() },
    React.createElement(AuthProvider, null,
      React.createElement('p', null, 'Sensitive fictional patient content'),
    ),
  ));

  assert.match(html, /Sign-out could not be confirmed/);
  assert.match(html, /Retry sign-out/);
  assert.doesNotMatch(html, /Sensitive fictional patient content/);
});

for (const pendingLogin of ['profile', 'unknown']) {
  test(`pending ${pendingLogin} session shows a retry and blocks another password submission`, () => {
    const html = renderLogin(pendingLogin);
    const submitButton = html.match(/<button[^>]*>Sign in<\/button>/)?.[0];

    assert.match(html, /Sign-in is not complete/);
    assert.match(html, /Retry session check/);
    assert.match(submitButton || '', /disabled=""/);
  });
}

test('normal sign-in displays a masked password and an enabled submit button', () => {
  const html = renderLogin(null);
  const submitButton = html.match(/<button[^>]*>Sign in<\/button>/)?.[0];

  assert.match(html, /type="password"/);
  assert.ok(submitButton);
  assert.doesNotMatch(submitButton, /disabled/);
  assert.doesNotMatch(html, /Retry session check/);
});

test('protected patient content renders only for an authenticated patient', () => {
  assert.doesNotMatch(renderGuard({ user: null }), /Sensitive fictional patient content/);
  assert.doesNotMatch(renderGuard({ user: { role: 'doctor' } }), /Sensitive fictional patient content/);
  assert.doesNotMatch(renderGuard({ user: { role: 'patient' }, loading: true }), /Sensitive fictional patient content/);
  assert.match(renderGuard({ user: { role: 'patient' } }), /Sensitive fictional patient content/);
});
