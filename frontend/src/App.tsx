import {
  ArrowRight,
  ArrowUp,
  ChevronDown,
  Clock3,
  Headphones,
  Menu,
  MessageSquareText,
  PanelLeftClose,
  Plus,
  RefreshCw,
  ShieldCheck,
  ThumbsDown,
  ThumbsUp,
  UserRound,
  Wrench,
  X,
} from "lucide-react";
import { FormEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";

import {
  ApiError,
  listConversations,
  listMessages,
  sendChat,
  sendMessageToHuman,
  submitConversationFeedback,
} from "./lib/api";
import type { ApiMessage, Conversation, DisplayMessage, ToolEvent } from "./types";
import RichText from "./RichText";

const CUSTOMER_ID = "customer-demo-001";

const suggestions = [
  {
    label: "订单与物流",
    description: "查询订单状态、发货进度和物流轨迹",
    text: "ORD-202608-1001 什么时候能到？",
  },
  {
    label: "售后与产品",
    description: "了解退换、维修和产品使用政策",
    text: "X3 Pro 买了 9 天出现质量问题，还能换货吗？",
  },
  {
    label: "账户与服务",
    description: "处理账户资料、安全设置和会员服务",
    text: "怎么修改账户绑定的手机号？",
  },
];

const toolLabels: Record<string, string> = {
  search_knowledge: "检索服务知识",
  get_order: "读取订单信息",
  get_logistics: "读取物流轨迹",
  create_ticket: "创建服务工单",
  request_human_handoff: "发起人工转接",
};

const statusLabels: Record<string, string> = {
  active: "AI 服务中",
  waiting_for_human: "等待人工接入",
  human_active: "人工服务中",
  resolved: "已解决",
  closed: "已结束",
};

function toDisplayMessage(message: ApiMessage): DisplayMessage {
  return {
    id: message.id,
    role: message.role === "system" ? "assistant" : message.role,
    content: message.content,
    createdAt: message.created_at,
  };
}

function formatTime(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

function formatConversationDate(value: string): string {
  const date = new Date(value);
  const now = new Date();
  if (date.toDateString() === now.toDateString()) return formatTime(value);
  return `${date.getMonth() + 1}/${date.getDate()}`;
}

function ToolTrace({ tools, rewrittenQuery }: { tools: ToolEvent[]; rewrittenQuery?: string | null }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="tool-trace">
      <button
        aria-expanded={open}
        className="tool-trace__summary"
        type="button"
        onClick={() => setOpen(!open)}
      >
        <span>系统查询记录</span>
        <small>{tools.length} 项已执行</small>
        <ChevronDown aria-hidden="true" className={open ? "is-open" : ""} size={15} />
      </button>
      {open && (
        <div className="tool-trace__details">
          {tools.map((tool, index) => (
            <div className="tool-row" key={`${tool.service_name}-${index}`}>
              <Wrench size={13} />
              <span>{toolLabels[tool.service_name] || tool.service_name}</span>
              <span className={`tool-status tool-status--${tool.status || "succeeded"}`}>
                {tool.status === "failed" ? "失败" : "完成"}
              </span>
            </div>
          ))}
          {rewrittenQuery && (
            <div className="rewrite-note">
              <RefreshCw size={13} />
              <span>为提高召回质量，系统将问题改写为：{rewrittenQuery}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function MessageBubble({ message }: { message: DisplayMessage }) {
  const isCustomer = message.role === "customer";
  const isHuman = message.role === "human_agent";

  return (
    <article className={`message message--${isCustomer ? "customer" : "service"}`}>
      {!isCustomer && (
        <div className={`message__avatar ${isHuman ? "message__avatar--human" : ""}`}>
          {isHuman ? <UserRound size={16} /> : <span>SL</span>}
        </div>
      )}
      <div className="message__body">
        <div className="message__meta">
          <span>{isCustomer ? "你" : isHuman ? "人工客服" : "ServiceLoop"}</span>
          <time>{formatTime(message.createdAt)}</time>
        </div>
        <div className="message__bubble"><RichText>{message.content}</RichText></div>
        {!isCustomer && message.tools && message.tools.length > 0 && (
          <ToolTrace tools={message.tools} rewrittenQuery={message.rewrittenQuery} />
        )}
        {message.handoffRequired && (
          <div className="handoff-card">
            <Headphones size={18} />
            <div>
              <strong>已连同上下文转入人工队列</strong>
              <p>人工客服可以看到本次问题、查询记录和转接原因，你无需重复描述。</p>
            </div>
          </div>
        )}
      </div>
    </article>
  );
}

function EmptyState({ onSelect }: { onSelect: (message: string) => void }) {
  return (
    <div className="service-intro">
      <section className="intro-copy">
        <h1>
          <span>你好，林先生。</span>
          我们来把事情处理清楚。
        </h1>
        <p>
          直接描述你的问题。订单和物流信息来自业务系统，政策回答会保留知识查询记录；
          遇到退款或你要求人工时，我们会立即转接。
        </p>
      </section>

      <div className="intro-grid">
        <section className="quick-services" aria-labelledby="quick-services-title">
          <div className="section-heading">
            <h2 id="quick-services-title">常用服务</h2>
            <small>选择一个示例开始</small>
          </div>
          <div className="service-list">
            {suggestions.map((item) => (
              <button key={item.label} type="button" onClick={() => onSelect(item.text)}>
                <span className="service-name">
                  <strong>{item.label}</strong>
                  <small>{item.description}</small>
                </span>
                <ArrowRight size={18} />
              </button>
            ))}
          </div>
        </section>

        <aside className="service-standard">
          <h2 className="standard-label">本次服务标准</h2>
          <div className="standard-item">
            <p><b>依据真实业务数据</b><span>订单与物流由服务工具查询</span></p>
          </div>
          <div className="standard-item">
            <p><b>回答过程可追踪</b><span>知识检索与工具调用均有记录</span></p>
          </div>
          <div className="standard-item">
            <p><b>高风险问题交给人工</b><span>退款和明确人工请求直接转接</span></p>
          </div>
        </aside>
      </div>
    </div>
  );
}

function App() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [feedbackState, setFeedbackState] = useState<"idle" | "submitting" | "submitted">("idle");
  const [feedbackRating, setFeedbackRating] = useState<number | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const activeConversation = useMemo(
    () => conversations.find((item) => item.id === activeId) || null,
    [activeId, conversations],
  );
  const conversationStatus = activeConversation?.status || "active";
  const isLocked = ["waiting_for_human", "resolved", "closed"].includes(conversationStatus);

  useEffect(() => {
    setFeedbackState("idle");
    setFeedbackRating(null);
  }, [activeId]);

  async function refreshConversations(preferredId?: string) {
    try {
      const items = await listConversations(CUSTOMER_ID);
      setConversations(items);
      if (preferredId) setActiveId(preferredId);
      setError(null);
      return items;
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "会话列表加载失败。");
      return [];
    }
  }

  useEffect(() => {
    void refreshConversations();
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  useEffect(() => {
    if (!activeId || !["waiting_for_human", "human_active"].includes(conversationStatus)) return;

    const poll = window.setInterval(() => {
      void Promise.all([
        listMessages(activeId, CUSTOMER_ID),
        listConversations(CUSTOMER_ID),
      ]).then(([history, items]) => {
        setMessages(history.map(toDisplayMessage));
        setConversations(items);
      }).catch(() => undefined);
    }, 2500);
    return () => window.clearInterval(poll);
  }, [activeId, conversationStatus]);

  async function openConversation(conversation: Conversation) {
    setActiveId(conversation.id);
    setSidebarOpen(false);
    setLoadingHistory(true);
    setError(null);
    try {
      const items = await listMessages(conversation.id, CUSTOMER_ID);
      setMessages(items.map(toDisplayMessage));
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "历史消息加载失败。");
    } finally {
      setLoadingHistory(false);
    }
  }

  function startNewConversation() {
    setActiveId(null);
    setMessages([]);
    setDraft("");
    setError(null);
    setSidebarOpen(false);
    requestAnimationFrame(() => textareaRef.current?.focus());
  }

  useEffect(() => {
    function handleShortcut(event: globalThis.KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        startNewConversation();
      }
    }

    window.addEventListener("keydown", handleShortcut);
    return () => window.removeEventListener("keydown", handleShortcut);
  }, []);

  async function submitMessage(text = draft) {
    const content = text.trim();
    if (!content || sending || isLocked) return;

    const optimistic: DisplayMessage = {
      id: `optimistic-${crypto.randomUUID()}`,
      role: "customer",
      content,
      createdAt: new Date().toISOString(),
    };
    setMessages((items) => [...items, optimistic]);
    setDraft("");
    setSending(true);
    setError(null);

    try {
      if (conversationStatus === "human_active" && activeId) {
        const response = await sendMessageToHuman({
          conversationId: activeId,
          customerId: CUSTOMER_ID,
          content,
        });
        setMessages((items) => items.map((item) => (
          item.id === optimistic.id ? toDisplayMessage(response) : item
        )));
        await refreshConversations(activeId);
        return;
      }
      const response = await sendChat({
        customerId: CUSTOMER_ID,
        conversationId: activeId || undefined,
        message: content,
      });
      setMessages((items) => [
        ...items,
        {
          id: response.assistant_message_id,
          role: "assistant",
          content: response.answer,
          createdAt: new Date().toISOString(),
          tools: response.tool_events,
          handoffRequired: response.handoff_required,
          handoffReason: response.handoff_reason,
          rewrittenQuery: response.rewritten_query,
        },
      ]);
      await refreshConversations(response.conversation_id);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "消息发送失败，请稍后重试。");
    } finally {
      setSending(false);
    }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    void submitMessage();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void submitMessage();
    }
  }

  async function submitFeedback(rating: number) {
    if (!activeId || feedbackState === "submitting") return;
    setFeedbackState("submitting");
    setError(null);
    try {
      await submitConversationFeedback({
        conversationId: activeId,
        customerId: CUSTOMER_ID,
        rating,
      });
      setFeedbackRating(rating);
      setFeedbackState("submitted");
    } catch (reason) {
      setFeedbackState("idle");
      setError(reason instanceof ApiError ? reason.message : "服务反馈提交失败，请稍后重试。");
    }
  }

  const lockedCopy: Partial<Record<string, { notice: string; placeholder: string }>> = {
    waiting_for_human: {
      notice: "当前服务已进入人工队列，请等待客服接入",
      placeholder: "人工客服接入后可继续沟通",
    },
    resolved: {
      notice: "本次服务已解决，如有新问题请新建服务",
      placeholder: "本次服务已解决",
    },
    closed: {
      notice: "本次服务已结束，如有新问题请新建服务",
      placeholder: "本次服务已结束",
    },
  };
  const currentLockedCopy = lockedCopy[conversationStatus];

  return (
    <div className="app-shell">
      {sidebarOpen && (
        <button className="sidebar-scrim" aria-label="关闭菜单" onClick={() => setSidebarOpen(false)} />
      )}
      <aside className={`sidebar ${sidebarOpen ? "is-open" : ""}`}>
        <div className="brand">
          <div className="brand__mark">SL</div>
          <div className="brand__wordmark">
            <strong>ServiceLoop</strong>
            <span>Service operations</span>
          </div>
          <button className="icon-button sidebar-close" type="button" aria-label="收起菜单" onClick={() => setSidebarOpen(false)}>
            <PanelLeftClose size={18} />
          </button>
        </div>

        <button className="new-chat" type="button" onClick={startNewConversation}>
          <Plus size={16} />
          新建服务
          <span>⌘ K</span>
        </button>

        <div className="conversation-heading">
          <span>服务记录</span>
          <small>{conversations.length.toString().padStart(2, "0")}</small>
        </div>
        <nav className="conversation-list" aria-label="历史对话">
          {conversations.map((conversation) => (
            <button
              className={conversation.id === activeId ? "is-active" : ""}
              key={conversation.id}
              type="button"
              onClick={() => void openConversation(conversation)}
            >
              <MessageSquareText size={15} />
              <span>
                <strong>{conversation.subject || "新的服务对话"}</strong>
                <small>{statusLabels[conversation.status]}</small>
              </span>
              <time>{formatConversationDate(conversation.updated_at)}</time>
            </button>
          ))}
          {conversations.length === 0 && (
            <p className="conversation-empty">完成一次咨询后，服务记录会保存在这里。</p>
          )}
        </nav>

        <div className="sidebar-meta">
          <span>人工服务时间</span>
          <strong>09:00 — 21:00</strong>
          <small>AI 服务全天可用</small>
        </div>
        <div className="profile">
          <span className="profile__avatar">林</span>
          <div><strong>林先生</strong><small>尊享会员 · ID 001</small></div>
          <ChevronDown size={15} />
        </div>
      </aside>

      <main className="chat-panel">
        <header className="chat-header">
          <button className="icon-button mobile-menu" type="button" aria-label="打开菜单" onClick={() => setSidebarOpen(true)}>
            <Menu size={20} />
          </button>
          <div className="chat-header__breadcrumb">
            <span>客户支持</span>
            <i>/</i>
            <strong>{activeConversation?.subject || "新建服务"}</strong>
          </div>
          <div aria-live="polite" className={`service-status service-status--${conversationStatus}`}>
            <span />
            {statusLabels[conversationStatus]}
          </div>
        </header>

        <section className="chat-content" aria-live="polite">
          {error && (
            <div className="error-banner" role="alert">
              <X size={16} />
              <p>{error}</p>
              <button type="button" onClick={() => setError(null)}>关闭</button>
            </div>
          )}
          {loadingHistory ? (
            <div className="history-loading" role="status"><RefreshCw size={19} /> 正在读取服务记录…</div>
          ) : messages.length === 0 ? (
            <EmptyState onSelect={(text) => void submitMessage(text)} />
          ) : (
            <div className="message-list">
              <div className="date-divider">
                <span>本次服务</span>
                <time>{new Intl.DateTimeFormat("zh-CN", { month: "long", day: "numeric" }).format(new Date())}</time>
              </div>
              {messages.map((message) => <MessageBubble key={message.id} message={message} />)}
              {sending && conversationStatus !== "human_active" && (
                <article className="message message--service">
                  <div className="message__avatar"><span>SL</span></div>
                  <div className="typing-card" role="status">
                    <div><span /><span /><span /></div>
                    <p>正在核对问题并查询业务系统</p>
                  </div>
                </article>
              )}
              <div ref={endRef} />
            </div>
          )}
        </section>

        <footer className="composer-area">
          {isLocked && (
            <div className="locked-notice"><Clock3 size={15} /> {currentLockedCopy?.notice}</div>
          )}
          {conversationStatus === "resolved" && activeId && (
            <div className="service-feedback" aria-live="polite">
              {feedbackState === "submitted" ? (
                <span>感谢反馈，{feedbackRating === 5 ? "这会帮助我们保留有效做法。" : "这条会话会进入运营复盘。"}</span>
              ) : (
                <>
                  <span>这次服务解决了你的问题吗？</span>
                  <button type="button" disabled={feedbackState === "submitting"} onClick={() => void submitFeedback(5)}><ThumbsUp size={14} />解决了</button>
                  <button type="button" disabled={feedbackState === "submitting"} onClick={() => void submitFeedback(2)}><ThumbsDown size={14} />仍有问题</button>
                </>
              )}
            </div>
          )}
          <form className="composer" onSubmit={handleSubmit}>
            <textarea
              ref={textareaRef}
              value={draft}
              aria-label="服务问题"
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={isLocked
                ? currentLockedCopy?.placeholder
                : conversationStatus === "human_active"
                  ? "回复人工客服…"
                  : "描述你的问题，或输入订单号…"}
              rows={1}
              disabled={sending || isLocked}
              maxLength={4000}
            />
            <div className="composer__footer">
              <span>Enter 发送&nbsp;&nbsp;·&nbsp;&nbsp;Shift + Enter 换行</span>
              <button type="submit" aria-label="发送消息" disabled={!draft.trim() || sending || isLocked}>
                <ArrowUp size={18} />
              </button>
            </div>
          </form>
          <div className="service-assurance">
            <span><ShieldCheck size={13} /> 服务过程可追踪</span>
            <i />
            <span>隐私信息受保护</span>
          </div>
        </footer>
      </main>
    </div>
  );
}

export default App;
