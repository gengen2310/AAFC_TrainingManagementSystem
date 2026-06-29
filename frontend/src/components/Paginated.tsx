import { useState, useMemo, type ReactNode } from "react";

// Lightweight client-side pagination for large lists. Keeps the DOM small (renders one page at a time)
// without pulling in a virtualisation library. For very large datasets the backend should paginate;
// this guards the UI so a big squadron/curriculum list stays responsive.
export function usePagination<T>(items: T[], pageSize = 25) {
  const [page, setPage] = useState(0);
  const pageCount = Math.max(1, Math.ceil(items.length / pageSize));
  const clamped = Math.min(page, pageCount - 1);
  const slice = useMemo(
    () => items.slice(clamped * pageSize, clamped * pageSize + pageSize),
    [items, clamped, pageSize]
  );
  return { slice, page: clamped, pageCount, setPage, total: items.length, pageSize };
}

export function Pager({ page, pageCount, total, pageSize, onPage }: {
  page: number; pageCount: number; total: number; pageSize: number; onPage: (p: number) => void;
}): ReactNode {
  if (total <= pageSize) return null;
  const from = page * pageSize + 1;
  const to = Math.min(total, (page + 1) * pageSize);
  return (
    <div className="pager" role="navigation" aria-label="Pagination">
      <button className="btn-ghost" onClick={() => onPage(page - 1)} disabled={page === 0} aria-label="Previous page">‹ Prev</button>
      <span className="muted">{from}–{to} of {total}</span>
      <button className="btn-ghost" onClick={() => onPage(page + 1)} disabled={page >= pageCount - 1} aria-label="Next page">Next ›</button>
    </div>
  );
}
