import { useCallback, useEffect, useMemo, useState } from "react";
import { CreateDocModal } from "./CreateDocModal";
import { formatShortDate } from "../../utils/formatDate";
import { docTypeClass, docTypeLabel } from "./docConstants";
import {
  createDoc,
  fetchDocPage,
  fetchDocsCatalog,
  searchDocs,
  type DocCatalog,
  type DocPage,
  type DocSearchHit
} from "./docsApi";

export function DocsView({ initialDocumentId }: { initialDocumentId?: string | null }) {
  const [catalog, setCatalog] = useState<DocCatalog | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [page, setPage] = useState<DocPage | null>(null);
  const [pageLoading, setPageLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [searchResults, setSearchResults] = useState<DocSearchHit[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [expandedTeams, setExpandedTeams] = useState<Set<string>>(() => new Set());

  const loadCatalog = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchDocsCatalog();
      setCatalog(data);
      setExpandedTeams(new Set(data.groups.map((group) => group.team)));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load docs");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadCatalog();
  }, [loadCatalog]);

  const openPage = useCallback(async (sourceId: string) => {
    setSearch("");
    setSearchResults(null);
    setSelectedId(sourceId);
    setPage(null);
    setPageLoading(true);
    setError(null);
    try {
      setPage(await fetchDocPage(sourceId));
    } catch (reason) {
      setPage(null);
      setError(reason instanceof Error ? reason.message : "Unable to load document");
    } finally {
      setPageLoading(false);
    }
  }, []);

  useEffect(() => {
    if (initialDocumentId) void openPage(initialDocumentId);
  }, [initialDocumentId, openPage]);

  useEffect(() => {
    const needle = search.trim();
    if (!needle) {
      setSearchResults(null);
      return;
    }
    const handle = window.setTimeout(() => {
      setSearching(true);
      void searchDocs(needle)
        .then(setSearchResults)
        .catch((reason) => {
          setError(reason instanceof Error ? reason.message : "Search failed");
          setSearchResults([]);
        })
        .finally(() => setSearching(false));
    }, 250);
    return () => window.clearTimeout(handle);
  }, [search]);

  const teamOptions = useMemo(
    () => catalog?.groups.map((group) => group.team) ?? ["Platform"],
    [catalog]
  );

  function toggleTeam(team: string) {
    setExpandedTeams((current) => {
      const next = new Set(current);
      if (next.has(team)) next.delete(team);
      else next.add(team);
      return next;
    });
  }

  async function handleCreate(draft: {
    title: string;
    team: string;
    source_type: string;
    body: string;
  }) {
    const created = await createDoc(draft);
    await loadCatalog();
    await openPage(created.source_id);
  }

  const showSearchPanel = search.trim().length > 0;

  if (loading && !catalog) {
    return (
      <div className="docs-shell">
        <p className="board-muted">Loading knowledge base…</p>
      </div>
    );
  }

  return (
    <div className="docs-shell">
      <header className="docs-header">
        <div>
          <h1>Docs</h1>
        </div>
        <div className="docs-header-actions">
          <label className="board-search docs-search">
            <span className="board-search-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="18" height="18">
                <path
                  fill="currentColor"
                  d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"
                />
              </svg>
            </span>
            <input
              type="search"
              value={search}
              placeholder="Search all documents"
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>
          <button type="button" className="board-primary-btn" onClick={() => setCreateOpen(true)}>
            Create
          </button>
        </div>
      </header>

      {error && <p className="error board-inline-error">{error}</p>}

      <div className="docs-layout">
        <aside className="docs-sidebar" aria-label="Document library">
          {catalog?.groups.map((group) => {
            const expanded = expandedTeams.has(group.team);
            return (
              <section key={group.team} className="docs-sidebar-group">
                <button
                  type="button"
                  className="docs-sidebar-team"
                  aria-expanded={expanded}
                  onClick={() => toggleTeam(group.team)}
                >
                  <span className="docs-sidebar-chevron" aria-hidden="true">
                    {expanded ? "▾" : "▸"}
                  </span>
                  {group.team}
                  <span className="docs-sidebar-count">{group.pages.length}</span>
                </button>
                {expanded && (
                  <ul className="docs-sidebar-list">
                    {group.pages.map((item) => (
                      <li key={item.source_id}>
                        <button
                          type="button"
                          className={`docs-sidebar-link${
                            selectedId === item.source_id ? " active" : ""
                          }`}
                          onClick={() => void openPage(item.source_id)}
                        >
                          <span className="docs-sidebar-link-title">{item.title}</span>
                          <span className={`docs-type-chip ${docTypeClass(item.source_type)}`}>
                            {docTypeLabel(item.source_type)}
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            );
          })}
        </aside>

        <main className="docs-main">
          {showSearchPanel ? (
            <div className="docs-search-panel">
              <h2 className="docs-search-heading">
                {searching ? "Searching…" : `Results for “${search.trim()}”`}
              </h2>
              {!searching && searchResults?.length === 0 && (
                <p className="board-muted">No documents match your search.</p>
              )}
              <ul className="docs-search-list">
                {(searchResults ?? []).map((hit) => (
                  <li key={hit.source_id}>
                    <button
                      type="button"
                      className="docs-search-card"
                      onClick={() => void openPage(hit.source_id)}
                    >
                      <div className="docs-search-card-head">
                        <h3>{hit.title}</h3>
                        <span className={`docs-type-chip ${docTypeClass(hit.source_type)}`}>
                          {docTypeLabel(hit.source_type)}
                        </span>
                      </div>
                      <p className="docs-search-meta">
                        {hit.team} · {hit.source_id}
                      </p>
                      <p className="docs-search-snippet">{hit.snippet}</p>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ) : pageLoading ? (
            <p className="board-muted">Opening document…</p>
          ) : page ? (
            <article className="docs-article">
              <header className="docs-article-head">
                <p className="docs-article-breadcrumb">
                  {page.team} / <span>{page.source_id}</span>
                </p>
                <h2>{page.title}</h2>
                <div className="docs-article-meta">
                  <span className={`docs-type-chip ${docTypeClass(page.source_type)}`}>
                    {docTypeLabel(page.source_type)}
                  </span>
                  <span className="docs-article-updated">Updated {formatShortDate(page.updated_at)}</span>
                  <span className="docs-article-system">{page.source_system}</span>
                </div>
              </header>
              <div className="docs-article-body">
                {page.body.split("\n").map((line, index) => (
                  <p key={`${index}-${line.slice(0, 12)}`}>{line || "\u00a0"}</p>
                ))}
              </div>
            </article>
          ) : (
            <div className="docs-empty">
              <p className="eyebrow">Browse or search</p>
              <h2>Company knowledge</h2>
              <p>
                Pick a page from the library, search across all documents, or create a new page for
                your team.
              </p>
            </div>
          )}
        </main>
      </div>

      <CreateDocModal
        open={createOpen}
        teamOptions={teamOptions}
        onClose={() => setCreateOpen(false)}
        onCreate={handleCreate}
      />
    </div>
  );
}
