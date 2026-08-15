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
