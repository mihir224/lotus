import { accentBucket } from "../../utils/accentBucket";

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
  return `docs-type-accent-${accentBucket(sourceType, 5)}`;
}

export const DOC_TYPE_OPTIONS = Object.entries(DOC_TYPE_LABEL).map(([value, label]) => ({
  value,
  label
}));
