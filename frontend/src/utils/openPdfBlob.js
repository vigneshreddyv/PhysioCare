let pdfViewerEpoch = 0;
const activePdfViewers = new Map();

export function preparePdfViewer() {
  const viewer = window.open('', '_blank');
  if (!viewer) return null;

  activePdfViewers.set(viewer, pdfViewerEpoch);
  viewer.opener = null;
  viewer.document.title = 'Opening laboratory report…';
  viewer.document.body.textContent = 'Opening laboratory report…';
  return viewer;
}

export function showPdfBlob(viewer, blob) {
  if (!viewer || viewer.closed) {
    throw new Error('The PDF viewer was blocked. Allow pop-ups and try again.');
  }
  if (activePdfViewers.get(viewer) !== pdfViewerEpoch) {
    closePdfViewer(viewer);
    throw new Error('The PDF request was cancelled because the signed-in account changed.');
  }

  const url = URL.createObjectURL(blob);
  viewer.location.replace(url);
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

export function closePdfViewer(viewer) {
  activePdfViewers.delete(viewer);
  if (viewer && !viewer.closed) viewer.close();
}

export function cancelPdfViewers() {
  pdfViewerEpoch += 1;
  for (const viewer of activePdfViewers.keys()) closePdfViewer(viewer);
}
