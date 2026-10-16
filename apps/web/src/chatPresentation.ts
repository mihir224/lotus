export function hideEvidenceReferences(content: string): string {
  return content.replace(
    /\s*\[(?:\d+(?:\s*[-,]\s*\d+)*)\](?=[\s.,;:!?)]|$)/g,
    ""
  );
}
