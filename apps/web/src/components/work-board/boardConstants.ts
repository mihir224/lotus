import type { BoardIssueStatus, BoardIssueType } from "./workBoardApi";

export const BOARD_COLUMNS: { id: BoardIssueStatus; label: string }[] = [
  { id: "ready_to_start", label: "Ready to Start" },
  { id: "development", label: "Development" },
  { id: "review", label: "Review" },
  { id: "testing", label: "Testing" },
  { id: "done", label: "Done" }
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
