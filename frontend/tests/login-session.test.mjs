import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { establishLogin, isValidAuthProfile, retryLoginProfile } from '../src/context/loginSession.js';

function context({ postLogin, fetchProfile, recoverCsrf = async () => {} }) {
  const events = [];
  let pending = null;
  const setPending = (value) => { pending = value; events.push(['pending', value]); };
  return {
    args: {
      postLogin,
      fetchProfile,
      recoverCsrf,
      setCsrf: (value) => events.push(['csrf', value]),
      setPending,
    },
    events,
    get pending() { return pending; },
  };
}

test('login becomes ready only after the profile request succeeds', async () => {
  let resolveProfile;
  const profile = new Promise((resolve) => { resolveProfile = resolve; });
  const flow = context({
    postLogin: async () => ({ data: { csrf_token: 'fictional-csrf' } }),
    fetchProfile: () => profile,
  });
  const result = establishLogin(flow.args);

  await Promise.resolve();
  assert.deepEqual(flow.events, [['csrf', 'fictional-csrf'], ['pending', 'profile']]);
  resolveProfile({ role: 'patient' });
  assert.deepEqual(await result, { status: 'ready' });
  assert.equal(flow.pending, null);
});

test('a malformed or incomplete account response cannot initialize authentication', () => {
  const base = { id: 'fictional-id', email: 'patient@example.test', full_name: 'Test Patient', role: 'patient' };
  assert.equal(isValidAuthProfile({ ...base, profile: { id: 'fictional-profile' } }), true);
  assert.equal(isValidAuthProfile({ ...base, profile: null }), false);
  assert.equal(isValidAuthProfile({ ...base, role: 'unknown', profile: {} }), false);
  assert.equal(isValidAuthProfile({ ...base, id: '', profile: {} }), false);
  assert.equal(isValidAuthProfile({ ...base, role: 'admin', profile: null }), true);
});

test('failed profile fetch stays incomplete and retry fetches profile without another login POST', async () => {
  let loginPosts = 0;
  let profileGets = 0;
  const flow = context({
    postLogin: async () => { loginPosts += 1; return { data: { csrf_token: 'fictional-csrf' } }; },
    fetchProfile: async () => {
      profileGets += 1;
      if (profileGets === 1) throw new Error('profile service unavailable');
      return { role: 'patient' };
    },
  });

  assert.deepEqual(await establishLogin(flow.args), { status: 'profile_failed' });
  assert.equal(flow.pending, 'profile');
  assert.equal(loginPosts, 1);
  assert.deepEqual(await retryLoginProfile({ ...flow.args, pending: flow.pending }), { status: 'ready' });
  assert.equal(loginPosts, 1);
  assert.equal(profileGets, 2);
  assert.equal(flow.pending, null);
});

test('ambiguous login network failure checks the existing cookie session before another password POST', async () => {
  let loginPosts = 0;
  let csrfChecks = 0;
  const flow = context({
    postLogin: async () => { loginPosts += 1; throw { request: {} }; },
    recoverCsrf: async () => { csrfChecks += 1; },
    fetchProfile: async () => ({ role: 'doctor' }),
  });

  const result = await establishLogin(flow.args);
  assert.equal(result.status, 'login_failed');
  assert.equal(result.ambiguous, true);
  assert.equal(flow.pending, 'unknown');
  assert.deepEqual(await retryLoginProfile({ ...flow.args, pending: flow.pending }), { status: 'ready' });
  assert.equal(loginPosts, 1);
  assert.equal(csrfChecks, 1);
});

test('rejected authentication response does not create a pending login or fetch a profile', async () => {
  let profileGets = 0;
  const rejection = { response: { status: 401, data: { detail: 'Incorrect email or password' } } };
  const flow = context({
    postLogin: async () => { throw rejection; },
    fetchProfile: async () => { profileGets += 1; },
  });

  const result = await establishLogin(flow.args);
  assert.equal(result.status, 'login_failed');
  assert.equal(result.error, rejection);
  assert.equal(result.ambiguous, false);
  assert.equal(flow.pending, null);
  assert.equal(profileGets, 0);
});

test('retry clears ambiguity only after a definite no-session response', async () => {
  const flow = context({
    postLogin: async () => ({ data: { csrf_token: 'fictional-csrf' } }),
    recoverCsrf: async () => { throw { response: { status: 401 } }; },
    fetchProfile: async () => { throw new Error('must not fetch profile'); },
  });
  flow.args.setPending('unknown');

  assert.deepEqual(await retryLoginProfile({ ...flow.args, pending: flow.pending }), { status: 'no_session' });
  assert.equal(flow.pending, null);
});

test('transient retry failure keeps the session check available', async () => {
  const flow = context({
    postLogin: async () => ({ data: { csrf_token: 'fictional-csrf' } }),
    fetchProfile: async () => { throw new Error('network unavailable'); },
  });
  flow.args.setPending('profile');

  assert.deepEqual(await retryLoginProfile({ ...flow.args, pending: flow.pending }), { status: 'profile_failed' });
  assert.equal(flow.pending, 'profile');
});

test('rejected profile check releases the pending state for a new sign-in', async () => {
  const flow = context({
    postLogin: async () => ({ data: { csrf_token: 'fictional-csrf' } }),
    fetchProfile: async () => { throw { response: { status: 401 } }; },
  });
  flow.args.setPending('profile');

  assert.deepEqual(await retryLoginProfile({ ...flow.args, pending: flow.pending }), { status: 'no_session' });
  assert.equal(flow.pending, null);
});

test('login page keeps protected navigation behind confirmed profile and offers session-only retry', async () => {
  const [provider, page] = await Promise.all([
    readFile(new URL('../src/context/AuthContext.jsx', import.meta.url), 'utf8'),
    readFile(new URL('../src/pages/common/EmailLogin.jsx', import.meta.url), 'utf8'),
  ]);

  assert.match(provider, /if \(result\.status === 'ready'\) return true/);
  assert.match(provider, /fetchUserProfile\(\{ preserveCsrfOnFailure: true, throwOnFailure: true \}\)/);
  assert.match(provider, /if \(!isValidAuthProfile\(response\.data\)\) throw/);
  assert.match(page, /if \(success\) navigate\(from/);
  assert.match(page, /if \(await retryPendingLogin\(\)\) navigate\(from/);
  assert.match(page, /disabled=\{submitting \|\| Boolean\(pendingLogin\)\}/);
  assert.match(page, /Retry session check/);
});
