import type {
  ApiMessage,
  BadCase,
  ChatResponse,
  Conversation,
  CustomerFeedback,
  DataOperationsOverview,
  DataOperationsRun,
  HandoffDetail,
  HandoffSummary,
  ImprovementTask,
  KnowledgeDocument,
  KnowledgeDraft,
  KnowledgeGap,
  KnowledgeVersion,
  OperationsOverview,
} from "../types";

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000"
).replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
    });
  } catch {
    throw new ApiError("无法连接客服服务，请确认后端和 MySQL 已启动。", 0);
  }

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as {
      detail?: string;
    } | null;
    throw new ApiError(body?.detail || "服务暂时不可用，请稍后再试。", response.status);
  }

  return response.json() as Promise<T>;
}

export function listConversations(customerId: string): Promise<Conversation[]> {
  return request(`/api/customer/conversations?customer_id=${encodeURIComponent(customerId)}`);
}

export function listMessages(
  conversationId: string,
  customerId: string,
): Promise<ApiMessage[]> {
  return request(
    `/api/customer/conversations/${conversationId}/messages?customer_id=${encodeURIComponent(customerId)}`,
  );
}

export function sendChat(payload: {
  customerId: string;
  conversationId?: string;
  message: string;
}): Promise<ChatResponse> {
  return request("/api/customer/chat", {
    method: "POST",
    body: JSON.stringify({
      customer_id: payload.customerId,
      conversation_id: payload.conversationId || null,
      message: payload.message,
    }),
  });
}

export function sendMessageToHuman(payload: {
  conversationId: string;
  customerId: string;
  content: string;
}): Promise<ApiMessage> {
  return request(`/api/customer/conversations/${payload.conversationId}/messages`, {
    method: "POST",
    body: JSON.stringify({ customer_id: payload.customerId, content: payload.content }),
  });
}

export function submitConversationFeedback(payload: {
  conversationId: string;
  customerId: string;
  rating: number;
  comment?: string;
}): Promise<CustomerFeedback> {
  return request(`/api/customer/conversations/${payload.conversationId}/feedback`, {
    method: "POST",
    body: JSON.stringify({
      customer_id: payload.customerId,
      rating: payload.rating,
      comment: payload.comment || null,
    }),
  });
}

export function listHandoffs(statuses: string[]): Promise<HandoffSummary[]> {
  const query = new URLSearchParams();
  statuses.forEach((status) => query.append("status", status));
  return request(`/api/agent/handoffs${query.size ? `?${query.toString()}` : ""}`);
}

export function getHandoff(handoffId: string): Promise<HandoffDetail> {
  return request(`/api/agent/handoffs/${handoffId}`);
}

export function acceptHandoff(handoffId: string, agentId: string): Promise<HandoffDetail> {
  return request(`/api/agent/handoffs/${handoffId}/accept`, {
    method: "POST",
    body: JSON.stringify({ agent_id: agentId }),
  });
}

export function replyToCustomer(payload: {
  handoffId: string;
  agentId: string;
  content: string;
}): Promise<ApiMessage> {
  return request(`/api/agent/handoffs/${payload.handoffId}/messages`, {
    method: "POST",
    body: JSON.stringify({ agent_id: payload.agentId, content: payload.content }),
  });
}

export function resolveHandoff(payload: {
  handoffId: string;
  agentId: string;
  resolutionCode: string;
  actionTaken: string;
  replyToCustomer: string;
  internalNotes?: string;
}): Promise<HandoffDetail> {
  return request(`/api/agent/handoffs/${payload.handoffId}/resolve`, {
    method: "POST",
    body: JSON.stringify({
      agent_id: payload.agentId,
      resolution_code: payload.resolutionCode,
      action_taken: payload.actionTaken,
      reply_to_customer: payload.replyToCustomer,
      internal_notes: payload.internalNotes || null,
    }),
  });
}

export function getOperationsOverview(): Promise<OperationsOverview> {
  return request("/api/operations/overview");
}

export function listKnowledgeGaps(status = "pending"): Promise<KnowledgeGap[]> {
  return request(`/api/operations/knowledge-gaps?status=${encodeURIComponent(status)}`);
}

export function dismissKnowledgeGap(gapId: string): Promise<KnowledgeGap> {
  return request(`/api/operations/knowledge-gaps/${gapId}/dismiss`, { method: "POST" });
}

export function runKnowledgeAgent(gapIds: string[]): Promise<{
  processed_gap_count: number;
  drafts: KnowledgeDraft[];
  message: string;
}> {
  return request("/api/operations/knowledge-agent/run", {
    method: "POST",
    body: JSON.stringify({ gap_ids: gapIds, operator_id: "operations-demo-001" }),
  });
}

export function listKnowledgeDrafts(): Promise<KnowledgeDraft[]> {
  return request("/api/operations/knowledge-drafts");
}

export function updateKnowledgeDraft(
  draftId: string,
  payload: { title: string; content: string },
): Promise<KnowledgeDraft> {
  return request(`/api/operations/knowledge-drafts/${draftId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function publishKnowledgeDraft(draftId: string): Promise<{
  draft: KnowledgeDraft;
  document: KnowledgeDocument;
}> {
  return request(`/api/operations/knowledge-drafts/${draftId}/publish`, {
    method: "POST",
    body: JSON.stringify({ operator_id: "operations-demo-001" }),
  });
}

export function listKnowledgeDocuments(): Promise<KnowledgeDocument[]> {
  return request("/api/operations/knowledge-documents");
}

export function createKnowledgeDocument(payload: {
  title: string;
  content: string;
}): Promise<KnowledgeDocument> {
  return request("/api/operations/knowledge-documents", {
    method: "POST",
    body: JSON.stringify({ ...payload, operator_id: "operations-demo-001" }),
  });
}

export function updateKnowledgeDocument(
  documentId: string,
  payload: { title: string; content: string },
): Promise<KnowledgeDocument> {
  return request(`/api/operations/knowledge-documents/${documentId}`, {
    method: "PUT",
    body: JSON.stringify({ ...payload, operator_id: "operations-demo-001" }),
  });
}

export function listKnowledgeVersions(documentId: string): Promise<KnowledgeVersion[]> {
  return request(`/api/operations/knowledge-documents/${documentId}/versions`);
}

export function archiveKnowledgeDocument(documentId: string): Promise<KnowledgeDocument> {
  return request(`/api/operations/knowledge-documents/${documentId}`, { method: "DELETE" });
}

export function getDataOperationsOverview(): Promise<DataOperationsOverview> {
  return request("/api/operations/data-overview");
}

export function listBadCases(): Promise<BadCase[]> {
  return request("/api/operations/bad-cases");
}

export function listImprovementTasks(): Promise<ImprovementTask[]> {
  return request("/api/operations/improvement-tasks");
}

export function listDataOperationsRuns(): Promise<DataOperationsRun[]> {
  return request("/api/operations/data-agent/runs?limit=8");
}

export function runDataOperationsAgent(): Promise<{
  run: DataOperationsRun;
  bad_cases: BadCase[];
  improvement_tasks: ImprovementTask[];
}> {
  return request("/api/operations/data-agent/run", {
    method: "POST",
    body: JSON.stringify({ operator_id: "operations-demo-001" }),
  });
}

export function resolveImprovementTask(
  taskId: string,
  resolutionNotes: string,
): Promise<ImprovementTask> {
  return request(`/api/operations/improvement-tasks/${taskId}/resolve`, {
    method: "POST",
    body: JSON.stringify({
      operator_id: "operations-demo-001",
      resolution_notes: resolutionNotes,
    }),
  });
}

export function promoteImprovementTask(taskId: string): Promise<{
  task: ImprovementTask;
  knowledge_gap: KnowledgeGap;
}> {
  return request(`/api/operations/improvement-tasks/${taskId}/promote-to-knowledge-gap`, {
    method: "POST",
    body: JSON.stringify({ operator_id: "operations-demo-001" }),
  });
}
