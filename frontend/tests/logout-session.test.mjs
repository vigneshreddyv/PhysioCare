import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { LOGOUT_PENDING_KEY, readLogoutMarker, revokeSessionWithPrivacy } from '../src/context/logoutSession.js';

function harness(postLogout, refreshCsrf = async () => {}) {
  const events = [];
  const values = new Map();
  const args = {
    postLogout,
    refreshCsrf,
    clearCsrf: () => events.push('clear-csrf'),
    clearPrivateState: () => events.push('clear-private-state'),
    setStatus: (status) => events.push(status),
    storage: {
      setItem: (key, value) => values.set(key, value),
      removeItem: (key) => values.delete(key),
    },
  };
  return { args, events, values };
}

test('successful logout hides private state before revocation and confirms only after the server responds', async () => {
  let resolvePost;
  const post = new Promise((resolve) => { resolvePost = resolve; });
  const context = harness(() => post);
  const result = revokeSessionWithPrivacy(context.args);

  assert.deepEqual(context.events, ['clear-private-state', 'pending']);
  assert.equal(context.values.get(LOGOUT_PENDING_KEY), '1');

  resolvePost({ status: 204 });
  assert.equal(await result, true);
  assert.deepEqual(context.events, ['clear-private-state', 'pending', 'clear-csrf', null]);
  assert.equal(context.values.has(LOGOUT_PENDING_KEY), false);
});

test('network failure leaves server sign-out unconfirmed and keeps the retry marker and CSRF token', async () => {
  const context = harness(async () => { throw new Error('network unavailable'); });

  assert.equal(await revokeSessionWithPrivacy(context.args), false);
  assert.deepEqual(context.events, ['clear-private-state', 'pending', 'failed']);
  assert.equal(context.values.get(LOGOUT_PENDING_KEY), '1');
});

test('rejected server revocation does not claim success; explicit retry can refresh CSRF and revoke', async () => {
  let calls = 0;
  let csrfRefreshes = 0;
  const context = harness(
    async () => {
      calls += 1;
      if (calls <= 2) throw { response: { status: 403 } };
      return { status: 204 };
    },
    async () => { csrfRefreshes += 1; },
  );

  assert.equal(await revokeSessionWithPrivacy(context.args), false);
  assert.equal(calls, 1);
  assert.equal(csrfRefreshes, 0);
  assert.equal(context.values.get(LOGOUT_PENDING_KEY), '1');
  assert.deepEqual(context.events, ['clear-private-state', 'pending', 'failed']);

  assert.equal(await revokeSessionWithPrivacy({ ...context.args, retry: true }), true);
  assert.equal(calls, 3);
  assert.equal(csrfRefreshes, 1);
  assert.equal(context.values.has(LOGOUT_PENDING_KEY), false);
  assert.deepEqual(context.events.slice(-3), ['pending', 'clear-csrf', null]);
});

test('retry remains unconfirmed when the server still rejects revocation', async () => {
  const context = harness(async () => { throw { response: { status: 403 } }; });

  assert.equal(await revokeSessionWithPrivacy({ ...context.args, retry: true }), false);
  assert.equal(context.values.get(LOGOUT_PENDING_KEY), '1');
  assert.equal(context.events.at(-1), 'failed');
  assert.equal(context.events.includes('clear-csrf'), false);
});

test('unavailable session storage fails closed after private state is hidden', async () => {
  let posted = false;
  const context = harness(async () => { posted = true; });
  context.args.storage.setItem = () => { throw new Error('storage unavailable'); };

  assert.equal(await revokeSessionWithPrivacy(context.args), false);
  assert.equal(posted, false);
  assert.deepEqual(context.events, ['clear-private-state', 'pending', 'failed']);
});

test('unreadable session storage fails closed at startup', () => {
  assert.deepEqual(readLogoutMarker(() => { throw new Error('storage unavailable'); }), {
    storage: null,
    pending: true,
  });
  assert.deepEqual(readLogoutMarker(() => ({
    getItem: () => { throw new Error('blocked'); },
    setItem() {},
    removeItem() {},
  })), {
    storage: null,
    pending: true,
  });
  assert.deepEqual(readLogoutMarker(() => ({ getItem: () => null })), {
    storage: null,
    pending: true,
  });
});

test('sign-out retry can confirm server revocation when startup storage is unavailable', async () => {
  let posted = false;
  const context = harness(async () => { posted = true; });
  context.args.storage = null;

  assert.equal(await revokeSessionWithPrivacy({ ...context.args, retry: true }), true);
  assert.equal(posted, true);
  assert.deepEqual(context.events, ['clear-private-state', 'pending', 'clear-csrf', null]);
});

test('storage-unavailable retry can establish that no server session exists', async () => {
  let posts = 0;
  let sessionChecks = 0;
  const context = harness(async () => {
    posts += 1;
    throw { response: { status: 403 } };
  }, async () => { throw { response: { status: 401 } }; });
  context.args.storage = null;
  context.args.checkNoSession = async () => {
    sessionChecks += 1;
    throw { response: { status: 401 } };
  };

  assert.equal(await revokeSessionWithPrivacy({ ...context.args, retry: true }), true);
  assert.equal(posts, 1);
  assert.equal(sessionChecks, 1);
  assert.deepEqual(context.events, ['clear-private-state', 'pending', 'clear-csrf', null]);
});

test('storage-unavailable retry stays blocked when an active session is found', async () => {
  const context = harness(
    async () => { throw { response: { status: 403 } }; },
    async () => { throw { response: { status: 401 } }; },
  );
  context.args.storage = null;
  context.args.checkNoSession = async () => ({ status: 200 });

  assert.equal(await revokeSessionWithPrivacy({ ...context.args, retry: true }), false);
  assert.equal(context.events.at(-1), 'failed');
});

test('storage-unavailable retry stays blocked when session status is uncertain', async () => {
  const context = harness(
    async () => { throw { response: { status: 403 } }; },
    async () => { throw { response: { status: 401 } }; },
  );
  context.args.storage = null;
  context.args.checkNoSession = async () => { throw new Error('network unavailable'); };

  assert.equal(await revokeSessionWithPrivacy({ ...context.args, retry: true }), false);
  assert.equal(context.events.at(-1), 'failed');
});

test('auth provider gates protected content and callers navigate only on confirmed logout', async () => {
  const [provider, patient, navbar, sidebar] = await Promise.all([
    readFile(new URL('../src/context/AuthContext.jsx', import.meta.url), 'utf8'),
    readFile(new URL('../src/layouts/PatientLayout.jsx', import.meta.url), 'utf8'),
    readFile(new URL('../src/components/common/Navbar.jsx', import.meta.url), 'utf8'),
    readFile(new URL('../src/components/common/Sidebar.jsx', import.meta.url), 'utf8'),
  ]);

  assert.match(provider, /useState\(readLogoutMarker\)/);
  assert.match(provider, /if \(logoutStatus\) \{[\s\S]*?Retry sign-out[\s\S]*?\}\s+return \(/);
  for (const caller of [patient, navbar, sidebar]) {
    assert.match(caller, /if \(await logout\(\)\) navigate\('\/login', \{ replace: true \}\)/);
  }
});
