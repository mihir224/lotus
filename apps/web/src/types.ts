export type Mode = "auto" | "ask_company" | "meeting" | "code" | "document" | "research";

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
};
