export type ConversationStatus =
  | "active"
  | "waiting_for_human"
  | "human_active"
  | "resolved"
  | "closed";

export interface Conversation {
  id: string;
  customer_id: string;
  channel: string;
  subject: string | null;
  status: ConversationStatus;
  started_at: string;
  created_at: string;
  updated_at: string;
}

export interface ApiMessage {
  id: string;
  conversation_id: string;
  role: "customer" | "assistant" | "human_agent" | "system";
  source: string;
  content: string;
  created_at: string;
}

export interface ToolEvent {
  service_name: string;
  input?: Record<string, unknown>;
  result?: {
    ok?: boolean;
    data?: unknown;
    error_code?: string | null;
  };
  status?: "succeeded" | "failed";
}

export interface ChatResponse {
  conversation_id: string;
  conversation_status: ConversationStatus;
  customer_message_id: string;
  assistant_message_id: string;
  answer: string;
  handoff_required: boolean;
  handoff_reason: string | null;
  handoff: Record<string, unknown> | null;
  tool_events: ToolEvent[];
  original_query: string | null;
  rewritten_query: string | null;
  rewrite_count: number;
  customer_intent: string | null;
  evidence_decision: Record<string, unknown> | null;
}

export interface DisplayMessage {
  id: string;
  role: "customer" | "assistant" | "human_agent";
  content: string;
  createdAt: string;
  tools?: ToolEvent[];
  handoffRequired?: boolean;
  handoffReason?: string | null;
  rewrittenQuery?: string | null;
}

export type HandoffStatus = "queued" | "assigned" | "active" | "resolved" | "cancelled";

export interface HandoffSummary {
  id: string;
  conversation_id: string;
  customer_id: string;
  subject: string | null;
  reason_code: string;
  agent_summary: string;
  status: HandoffStatus;
  assigned_agent_id: string | null;
  requested_at: string;
  accepted_at: string | null;
  resolved_at: string | null;
  message_count: number;
  latest_message: string;
  updated_at: string;
}

export interface HandoffDetail extends HandoffSummary {
  reason_detail: string | null;
  customer_question: string;
  context_package: Record<string, unknown>;
  messages: ApiMessage[];
}

export interface OperationsOverview {
  published_documents: number;
  pending_gaps: number;
  open_drafts: number;
  index: {
    ready?: boolean;
    document_count?: number;
    chunk_count?: number;
    index_version?: number;
    storage?: string;
  };
}

export interface KnowledgeGap {
  id: string;
  conversation_id: string | null;
  question: string;
  reason: string;
  evidence: Record<string, unknown>;
  status: "pending" | "drafted" | "resolved" | "dismissed";
  draft_id: string | null;
  human_resolution: {
    resolution_code: string;
    action_taken: string;
    reply_to_customer: string;
  } | null;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeDraft {
  id: string;
  title: string;
  content: string;
  gap_ids: string[];
  status: "draft" | "published" | "discarded";
  generated_by: string;
  generation_notes: string | null;
  published_document_id: string | null;
  published_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeDocument {
  id: string;
  title: string;
  content: string;
  source: string;
  status: "published" | "archived";
  current_version: number;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeVersion {
  id: string;
  document_id: string;
  version: number;
  title: string;
  content: string;
  created_by: string;
  published_at: string;
}

export interface CustomerFeedback {
  id: string;
  conversation_id: string;
  customer_id: string;
  rating: number;
  comment: string | null;
  source: string;
  created_at: string;
  updated_at: string;
}

export interface BadCase {
  id: string;
  signal_key: string;
  conversation_id: string | null;
  category: "knowledge" | "tool" | "experience" | "process" | string;
  severity: "high" | "medium" | "low" | string;
  summary: string;
  evidence: Record<string, unknown>;
  source_type: string;
  source_id: string;
  status: "open" | "tasked" | "resolved" | "dismissed";
  created_at: string;
  updated_at: string;
}

export interface ImprovementTask {
  id: string;
  category: string;
  title: string;
  description: string;
  bad_case_ids: string[];
  evidence: Record<string, unknown>;
  status: "open" | "resolved";
  owner_id: string | null;
  linked_knowledge_gap_id: string | null;
  resolution_notes: string | null;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface DataOperationsRun {
  id: string;
  operator_id: string;
  status: string;
  processed_signal_count: number;
  created_bad_case_count: number;
  created_task_count: number;
  summary: string;
  findings: Array<Record<string, unknown>>;
  created_at: string;
}

export interface DataOperationsOverview {
  feedback_total: number;
  negative_feedback: number;
  failed_tool_calls: number;
  open_bad_cases: number;
  open_improvement_tasks: number;
  latest_run: DataOperationsRun | null;
}
