export function preparePdfViewer() {
  const viewer = window.open('', '_blank');
  if (!viewer) return null;

  viewer.opener = null;
  viewer.document.title = 'Opening laboratory report…';
  viewer.document.body.textContent = 'Opening laboratory report…';
  return viewer;
}

export function showPdfBlob(viewer, blob) {
  if (!viewer || viewer.closed) {
    throw new Error('The PDF viewer was blocked. Allow pop-ups and try again.');
  }

  const url = URL.createObjectURL(blob);
  viewer.location.replace(url);
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

export function closePdfViewer(viewer) {
  if (viewer && !viewer.closed) viewer.close();
}
