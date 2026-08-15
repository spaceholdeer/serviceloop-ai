import type {
  ApiMessage,
  ChatResponse,
  Conversation,
  HandoffDetail,
  HandoffSummary,
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
