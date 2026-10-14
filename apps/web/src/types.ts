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
};

export type MeetingRecord = {
  meeting_id: string;
  transcript: {
    recording_url: string | null;
    title: string;
  };
  analysis: MeetingAnalysis | null;
};

export type GroundedAnswer = {
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
  artifacts: { artifact_type: string; title: string; content: string | object }[];
};
