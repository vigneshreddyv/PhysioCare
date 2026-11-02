import { useDeferredValue, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchClinicalPage } from '../../services/clinicalPagination';
import ClinicalPageNav from '../../components/common/ClinicalPageNav';

// Each query retains one authorized page. The chosen record remains visible when
// the operator searches or navigates, while the final mutation rechecks its ID.
export default function ClinicalEntityPicker({ path, label, selected, onSelect, describe }) {
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const deferredSearch = useDeferredValue(search);
  const searchSettled = deferredSearch === search;
  const queryPath = `${path}${path.includes('?') ? '&' : '?'}search=${encodeURIComponent(deferredSearch.trim())}`;
  const directory = useQuery({
    queryKey: ['clinicalEntityPicker', path, deferredSearch, page],
    queryFn: () => fetchClinicalPage(queryPath, page),
    gcTime: 0,
  });
  const choices = searchSettled ? directory.data?.data || [] : [];
  const visible = selected && !choices.some((item) => item.id === selected.id)
    ? [selected, ...choices] : choices;
  return <div className="grid gap-2">
    <label htmlFor={`${label}-search`}>Search {label.toLowerCase()}</label>
    <input id={`${label}-search`} type="search" value={search}
      onChange={(event) => { setSearch(event.target.value); setPage(1); }}
      className="min-h-11 rounded-xl border border-outline-variant px-3"
      placeholder={`Search ${label.toLowerCase()} by name or email`} />
    {directory.isError && <p role="alert">Could not load {label.toLowerCase()}. <button type="button" onClick={() => directory.refetch()}>Retry</button></p>}
    <select aria-label={label} value={selected?.id || ''} disabled={(directory.isPending || !searchSettled) && !selected}
      onChange={(event) => onSelect(visible.find((item) => item.id === event.target.value) || null)}
      className="min-h-11 rounded-xl border border-outline-variant bg-surface px-3">
      <option value="">Select {label.toLowerCase()}</option>
      {visible.map((item) => <option key={item.id} value={item.id}>{describe(item)}</option>)}
    </select>
    {(directory.isPending || !searchSettled) && <p role="status">Loading {label.toLowerCase()}…</p>}
    {searchSettled && !directory.isPending && !directory.isError && choices.length === 0 && <p>No matching {label.toLowerCase()} on this page.</p>}
    <ClinicalPageNav label={label} page={page} onPageChange={setPage}
      isLoading={directory.isFetching || !searchSettled} itemCount={choices.length} hasNext={directory.data?.hasNext} />
  </div>;
}
