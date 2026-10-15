import { authHeaders } from "../../auth";

export type BoardIssueStatus =
  | "ready_to_start"
  | "development"
  | "review"
  | "testing"
  | "done";

export type BoardIssueType = "bug" | "user_story";

export type BoardIssuePriority = "low" | "medium" | "high";

export const BOARD_ISSUE_UNASSIGNED = "unassigned";

export type BoardIssue = {
  issue_key: string;
  project_id: string;
  team_id: string;
  title: string;
  issue_type: BoardIssueType;
  feature_key: string;
  feature_title: string;
  description: string;
  acceptance_criteria: string[];
  priority: BoardIssuePriority;
  story_points: number;
  sprint: string | null;
  reporter_id: string;
  status: BoardIssueStatus;
  assignee_id: string;
};

export type BoardAssignee = {
  assignee_id: string;
  name: string;
  initials: string;
  avatar_color: string;
};

export type BoardTeam = {
  team_id: string;
  name: string;
  key_prefix: string;
};

export type WorkBoardPayload = {
  board: {
    project_id: string;
    project_name: string;
    board_title: string;
  };
  teams: BoardTeam[];
  assignees: BoardAssignee[];
  issues: BoardIssue[];
};

export type BoardIssuePatch = {
  title?: string;
  issue_type?: BoardIssueType;
  status?: BoardIssueStatus;
  assignee_id?: string;
  description?: string;
  acceptance_criteria?: string[];
  priority?: BoardIssuePriority;
  story_points?: number;
  reporter_id?: string;
};

export type BoardIssueCreatePayload = {
  title: string;
  project_id: string;
  team_id: string;
  feature_key: string;
  issue_type?: BoardIssueType;
  status?: BoardIssueStatus;
  assignee_id?: string;
  reporter_id?: string;
  description?: string;
  acceptance_criteria?: string[];
  priority?: BoardIssuePriority;
  story_points?: number;
};

export async function fetchWorkBoard(
  projectId: string,
  teamId: string
): Promise<WorkBoardPayload> {
  const params = new URLSearchParams({ project_id: projectId, team_id: teamId });
  const response = await fetch(`/v1/work-board?${params}`, { headers: authHeaders() });
  if (!response.ok) throw new Error(`Work board failed with ${response.status}`);
  return response.json() as Promise<WorkBoardPayload>;
}

export async function patchBoardIssue(
  issueKey: string,
  patch: BoardIssuePatch
): Promise<BoardIssue> {
  const response = await fetch(`/v1/work-board/issues/${encodeURIComponent(issueKey)}`, {
    method: "PATCH",
    headers: authHeaders(true),
    body: JSON.stringify(patch)
  });
  if (!response.ok) throw new Error(`Update failed with ${response.status}`);
  return response.json() as Promise<BoardIssue>;
}

export async function createBoardIssue(payload: BoardIssueCreatePayload): Promise<BoardIssue> {
  const response = await fetch("/v1/work-board/issues", {
    method: "POST",
    headers: authHeaders(true),
    body: JSON.stringify(payload)
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
  return response.json() as Promise<BoardIssue>;
}
