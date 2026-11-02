import test from 'node:test';
import assert from 'node:assert/strict';

import {
  cancelPdfViewers,
  preparePdfViewer,
  showPdfBlob,
} from '../src/utils/openPdfBlob.js';

function makeViewer() {
  return {
    closed: false,
    document: { title: '', body: { textContent: '' } },
    location: { replace(value) { this.value = value; } },
    close() { this.closed = true; },
  };
}

test('an authentication change closes viewers and rejects a stale PDF response', () => {
  const viewer = makeViewer();
  const originalWindow = globalThis.window;
  globalThis.window = { open: () => viewer, setTimeout: () => 1 };
  try {
    assert.equal(preparePdfViewer(), viewer);
    cancelPdfViewers();
    assert.equal(viewer.closed, true);
    assert.throws(
      () => showPdfBlob(viewer, new Blob(['pdf'])),
      /viewer was blocked|account changed/,
    );
  } finally {
    globalThis.window = originalWindow;
  }
});

test('a current viewer receives the PDF blob and is later closed on auth change', () => {
  const viewer = makeViewer();
  const originalWindow = globalThis.window;
  const originalCreateObjectURL = URL.createObjectURL;
  const originalRevokeObjectURL = URL.revokeObjectURL;
  globalThis.window = { open: () => viewer, setTimeout: (callback) => { callback(); return 1; } };
  URL.createObjectURL = () => 'blob:physiocare-report';
  URL.revokeObjectURL = () => {};
  try {
    preparePdfViewer();
    showPdfBlob(viewer, new Blob(['pdf']));
    assert.equal(viewer.location.value, 'blob:physiocare-report');
    cancelPdfViewers();
    assert.equal(viewer.closed, true);
  } finally {
    globalThis.window = originalWindow;
    URL.createObjectURL = originalCreateObjectURL;
    URL.revokeObjectURL = originalRevokeObjectURL;
  }
});
