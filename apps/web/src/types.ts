export type Evidence = {
  source_id: string;
  source_system: string;
  source_type: string;
  title: string | null;
  uri: string | null;
  snippet: string;
  section: string | null;
  updated_at: string | null;
  retrieval_method: string;
  score: number | null;
  navigation_target?: NavigationTarget | null;
};

export type NavigationTarget = {
  kind: "meeting" | "document" | "project" | "planning_item";
  entity_id: string;
  project_id: string | null;
  label: string;
  timestamp_ms: number | null;
};

export type CalendarEvent = {
  event_id: string;
  meeting_id: string;
  project_id: string;
  title: string;
  organizer: string;
  organizer_initials: string;
  location: string | null;
  description: string;
  started_at: string;
  ended_at: string;
  canceled: boolean;
  recurring: boolean;
};

export type MeetingAnalysis = {
  summary: string;
  decisions: { text: string }[];
  action_items: { text: string; owner: string | null; due_date: string | null }[];
  open_questions: string[];
  anomalies?: { anomaly_type: string; severity: string; description: string; evidence_segment_ids: string[] }[];
  clarifications_needed?: {
    kind: "open_question" | "anomaly" | "decision_conflict";
    text: string;
    severity: "low" | "medium" | "high";
    evidence_segment_ids: string[];
  }[];
};

export type MeetingRecord = {
  meeting_id: string;
  transcript: {
    recording_url: string | null;
    title: string;
    started_at: string;
    participants: string[];
    language_code: string;
    segments: {
      segment_id: string;
      start_ms: number;
      end_ms: number;
      speaker: string;
      text: string;
    }[];
  };
  analysis: MeetingAnalysis | null;
};

export type GroundedAnswer = {
  execution_id: string;
  answer: string;
  evidence: Evidence[];
  scope: {
    tenant_id: string;
    project_id: string | null;
    meeting_id: string | null;
    repository_id: string | null;
  };
  uncertainty: string[];
  next_action: string | null;
  route: {
    route: string;
    confidence: number;
    reason: string;
    live_retrieval: boolean;
  };
  agents_used: string[];
  plan: {
    steps: { agent: string; intent: string; depends_on: string[] }[];
    reason: string;
    date_from: string | null;
    date_to: string | null;
  } | null;
  artifacts: { artifact_type: string; title: string; content: string | object; navigation_target?: NavigationTarget | null }[];
  navigation_targets: NavigationTarget[];
  session_id: string | null;
};

export type ChatMessage = {
  message_id: string;
  session_id: string;
  role: "user" | "assistant";
  content: string;
  execution_id: string | null;
  status: "running" | "completed" | "failed";
  response: GroundedAnswer | null;
  created_at: string;
};

export type ChatSession = {
  session_id: string;
  title: string;
  project_id: string;
  created_at: string;
  updated_at: string;
};

export type ChatSessionDetail = { session: ChatSession; messages: ChatMessage[] };

export type RunEvent = {
  event_type: "run.started" | "node.started" | "node.completed" | "node.failed" |
    "answer.delta" | "answer.completed" | "run.failed" | "heartbeat";
  execution_id: string;
  session_id: string | null;
  timestamp: string;
  node_id: string | null;
  parent_id: string | null;
  node_kind: "agent" | "tool" | null;
  label: string | null;
  status: "pending" | "running" | "completed" | "failed" | null;
  duration_ms: number | null;
  input_preview: Record<string, unknown> | null;
  output_preview: Record<string, unknown> | null;
  answer_delta: string | null;
  response: GroundedAnswer | null;
  error: string | null;
};
