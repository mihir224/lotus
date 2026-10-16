import { authHeaders } from "../../auth";

export type DocSourceSummary = {
  source_id: string;
  title: string;
  team: string;
  source_type: string;
  source_system: string;
  updated_at: string | null;
};

export type DocTeamGroup = {
  team: string;
  pages: DocSourceSummary[];
};

export type DocCatalog = {
  project_id: string;
  groups: DocTeamGroup[];
};

export type DocPage = {
  source_id: string;
  project_id: string;
  title: string;
  team: string;
  source_type: string;
  source_system: string;
  source_uri: string | null;
  body: string;
  updated_at: string | null;
};

export type DocSearchHit = {
  source_id: string;
  title: string;
  team: string;
  source_type: string;
  snippet: string;
  updated_at: string | null;
};

export type DocCreatePayload = {
  title: string;
  team: string;
  source_type: string;
  body: string;
};

export type DocUpdatePayload = DocCreatePayload;

const PROJECT_ID = "payments";

export async function fetchDocsCatalog(): Promise<DocCatalog> {
  const params = new URLSearchParams({ project_id: PROJECT_ID });
  const response = await fetch(`/v1/docs/catalog?${params}`, { headers: authHeaders() });
  if (!response.ok) throw new Error(`Docs catalog failed with ${response.status}`);
  return response.json() as Promise<DocCatalog>;
}

export async function fetchDocPage(sourceId: string): Promise<DocPage> {
  const params = new URLSearchParams({ project_id: PROJECT_ID });
  const response = await fetch(
    `/v1/docs/sources/${encodeURIComponent(sourceId)}?${params}`,
    { headers: authHeaders() }
  );
  if (!response.ok) throw new Error(`Doc failed with ${response.status}`);
  return response.json() as Promise<DocPage>;
}

export async function searchDocs(query: string): Promise<DocSearchHit[]> {
  const params = new URLSearchParams({ project_id: PROJECT_ID, q: query });
  const response = await fetch(`/v1/docs/search?${params}`, { headers: authHeaders() });
  if (!response.ok) throw new Error(`Doc search failed with ${response.status}`);
  return response.json() as Promise<DocSearchHit[]>;
}

export async function createDoc(payload: DocCreatePayload): Promise<DocPage> {
  const response = await fetch("/v1/docs/sources", {
    method: "POST",
    headers: authHeaders(true),
    body: JSON.stringify({ ...payload, project_id: PROJECT_ID })
  });
  if (!response.ok) {
    let detail = `Create failed with ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return response.json() as Promise<DocPage>;
}

export async function updateDoc(
  sourceId: string,
  payload: DocUpdatePayload
): Promise<DocPage> {
  const params = new URLSearchParams({ project_id: PROJECT_ID });
  const response = await fetch(
    `/v1/docs/sources/${encodeURIComponent(sourceId)}?${params}`,
    {
      method: "PUT",
      headers: authHeaders(true),
      body: JSON.stringify(payload)
    }
  );
  if (!response.ok) throw new Error(`Update failed with ${response.status}`);
  return response.json() as Promise<DocPage>;
}

export async function deleteDoc(sourceId: string): Promise<void> {
  const params = new URLSearchParams({ project_id: PROJECT_ID });
  const response = await fetch(
    `/v1/docs/sources/${encodeURIComponent(sourceId)}?${params}`,
    { method: "DELETE", headers: authHeaders() }
  );
  if (!response.ok) throw new Error(`Delete failed with ${response.status}`);
}
