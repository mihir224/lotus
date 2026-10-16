import type { BoardIssueStatus, BoardIssueType } from "./workBoardApi";

export const BOARD_COLUMNS: { id: BoardIssueStatus; label: string; dotClass: string }[] = [
  { id: "ready_to_start", label: "Ready to Start", dotClass: "board-column-dot-ready" },
  { id: "development", label: "Development", dotClass: "board-column-dot-dev" },
  { id: "review", label: "Review", dotClass: "board-column-dot-review" },
  { id: "testing", label: "Testing", dotClass: "board-column-dot-testing" },
  { id: "done", label: "Done", dotClass: "board-column-dot-done" }
];

export const ISSUE_TYPE_LABEL: Record<BoardIssueType, string> = {
  user_story: "User story",
  bug: "Bug"
};

export function statusLabel(status: BoardIssueStatus): string {
  return BOARD_COLUMNS.find((column) => column.id === status)?.label ?? status;
}

export function priorityLabel(priority: string): string {
  return priority.charAt(0).toUpperCase() + priority.slice(1);
}

export function featureAccentClass(featureKey: string): string {
  const code = featureKey.split("-").pop() ?? "0";
  const bucket = Number.parseInt(code, 10) % 4;
  return `board-feature-accent-${bucket}`;
}

/** Readable initials on assignee avatar circles (light pastels → dark text). */
export function avatarInitialsColor(avatarColor: string): string {
  const normalized = avatarColor.trim().replace(/^#/, "");
  if (normalized.length !== 6 || !/^[0-9a-fA-F]+$/.test(normalized)) {
    return "#f0f4f2";
  }
  const r = Number.parseInt(normalized.slice(0, 2), 16);
  const g = Number.parseInt(normalized.slice(2, 4), 16);
  const b = Number.parseInt(normalized.slice(4, 6), 16);
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luminance > 0.58 ? "#1a2e28" : "#f0f4f2";
}
