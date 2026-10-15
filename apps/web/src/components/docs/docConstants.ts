export const DOC_TYPE_LABEL: Record<string, string> = {
  architecture: "Architecture",
  runbook: "Runbook",
  product: "Product",
  adr: "ADR",
  policy: "Policy",
  issue: "Issue",
  product_doc: "Product doc",
  release_note: "Release note",
  guide: "Guide"
};

export function docTypeLabel(sourceType: string): string {
  return DOC_TYPE_LABEL[sourceType] ?? sourceType.replace(/_/g, " ");
}

export function docTypeClass(sourceType: string): string {
  const bucket =
    Math.abs(sourceType.split("").reduce((sum, char) => sum + char.charCodeAt(0), 0)) % 5;
  return `docs-type-accent-${bucket}`;
}

export const DOC_TYPE_OPTIONS = Object.entries(DOC_TYPE_LABEL).map(([value, label]) => ({
  value,
  label
}));
