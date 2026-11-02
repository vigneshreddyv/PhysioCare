import { useEffect, useState } from 'react';
import { MAX_CLINICAL_PAGE } from '../../services/clinicalPagination';

export default function ClinicalPageNav({ label, page, onPageChange, isLoading, itemCount, hasNext = true }) {
  const [draft, setDraft] = useState(String(page));
  const inputId = `${label.toLowerCase().replace(/[^a-z0-9]+/g, '-')}-page`;
  useEffect(() => setDraft(String(page)), [page]);

  const go = (next) => {
    if (!Number.isInteger(next) || next < 1 || next > MAX_CLINICAL_PAGE || isLoading) return;
    onPageChange(next);
  };

  return <nav className="flex flex-wrap items-center gap-3 p-4" aria-label={`${label} pages`}>
    <button type="button" className="portal-inline-action" disabled={page === 1 || isLoading} onClick={() => go(page - 1)}>Previous page</button>
    <form onSubmit={(event) => { event.preventDefault(); go(Number(draft)); }} className="flex items-center gap-2">
      <label htmlFor={inputId}>Page</label>
      <input id={inputId} type="number" min="1" max={MAX_CLINICAL_PAGE} value={draft} onChange={(event) => setDraft(event.target.value)} className="w-20 rounded-lg border border-outline-variant px-2 py-1" />
      <button type="submit" className="portal-inline-action" disabled={isLoading}>Go</button>
    </form>
    <span aria-live="polite">Showing {itemCount} on page {page}</span>
    <button type="button" className="portal-inline-action" disabled={isLoading || !hasNext || page >= MAX_CLINICAL_PAGE} onClick={() => go(page + 1)}>Next page</button>
  </nav>;
}
