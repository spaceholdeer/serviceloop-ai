import {
  ArrowLeft,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleUserRound,
  Clock3,
  Headphones,
  Inbox,
  MessageSquareText,
  PanelRightOpen,
  RefreshCw,
  Search,
  Send,
  ShieldAlert,
  Tag,
  UserRoundCheck,
  X,
} from "lucide-react";
import {
  FormEvent,
  KeyboardEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  acceptHandoff,
  ApiError,
  getHandoff,
  listHandoffs,
  replyToCustomer,
  resolveHandoff,
} from "./lib/api";
import type { ApiMessage, HandoffDetail, HandoffSummary } from "./types";
import RichText from "./RichText";

const AGENT_ID = "agent-demo-001";

const reasonLabels: Record<string, string> = {
  refund_request: "退款申请",
  user_requested_human: "客户指定人工",
  knowledge_insufficient: "知识不足",
  policy_unclear: "规则不明确",
  tool_failed: "业务查询失败",
  query_rewrite_failed: "问题改写失败",
  knowledge_not_found: "未检索到知识",
  risk_case: "风险问题",
};

const statusLabels: Record<string, string> = {
  queued: "待接入",
  assigned: "已分配",
  active: "处理中",
  resolved: "已解决",
  cancelled: "已取消",
};

const filters = [
  { id: "open", label: "未解决", statuses: ["queued", "assigned", "active"] },
  { id: "queued", label: "待接入", statuses: ["queued"] },
  { id: "active", label: "处理中", statuses: ["assigned", "active"] },
  { id: "resolved", label: "已解决", statuses: ["resolved"] },
] as const;

type FilterId = (typeof filters)[number]["id"];

function formatClock(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

function formatWait(value: string): string {
  const minutes = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 60000));
  if (minutes < 1) return "刚刚";
  if (minutes < 60) return `${minutes} 分钟`;
  return `${Math.floor(minutes / 60)} 小时 ${minutes % 60} 分钟`;
}

function getObject(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

function MessageRow({ message }: { message: ApiMessage }) {
  const isCustomer = message.role === "customer";
  const isHuman = message.role === "human_agent";
  return (
    <article className={`agent-message agent-message--${isCustomer ? "customer" : "service"}`}>
      <div className={`agent-message__avatar ${isHuman ? "is-human" : ""}`}>
        {isCustomer ? <CircleUserRound size={17} /> : isHuman ? <UserRoundCheck size={16} /> : <span>SL</span>}
      </div>
      <div className="agent-message__content">
        <div className="agent-message__meta">
          <strong>{isCustomer ? "林先生" : isHuman ? "人工客服" : "ServiceLoop Agent"}</strong>
          <time>{formatClock(message.created_at)}</time>
        </div>
        <p><RichText>{message.content}</RichText></p>
      </div>
    </article>
  );
}

function ContextPanel({
  handoff,
  resolving,
  onCloseResolution,
  mobileOpen,
  onMobileClose,
  onResolve,
}: {
  handoff: HandoffDetail;
  resolving: boolean;
  onCloseResolution: () => void;
  mobileOpen: boolean;
  onMobileClose: () => void;
  onResolve: (payload: { action: string; reply: string; notes: string }) => Promise<void>;
}) {
  const [action, setAction] = useState("");
  const [reply, setReply] = useState("");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const context = handoff.context_package;
  const orderId = typeof context.order_id === "string" ? context.order_id : null;
  const toolEvents = Array.isArray(context.tool_events) ? context.tool_events : [];
  const gap = getObject(context.knowledge_gap_assessment);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!action.trim() || !reply.trim() || saving) return;
    setSaving(true);
    try {
      await onResolve({ action: action.trim(), reply: reply.trim(), notes: notes.trim() });
    } finally {
      setSaving(false);
    }
  }

  if (resolving) {
    return (
      <aside className={`agent-context resolution-panel ${mobileOpen ? "is-mobile-open" : ""}`} aria-label="完成服务">
        <div className="context-title">
          <div><strong>完成本次服务</strong><span>结论将写入人工处理记录</span></div>
          <button type="button" aria-label="关闭完成表单" onClick={onCloseResolution}><X size={17} /></button>
        </div>
        <form onSubmit={submit}>
          <label>
            <span>已采取的处理</span>
            <textarea value={action} onChange={(event) => setAction(event.target.value)} placeholder="例如：核对订单后提交退款申请" rows={3} maxLength={4000} />
          </label>
          <label>
            <span>给客户的最终回复</span>
            <textarea value={reply} onChange={(event) => setReply(event.target.value)} placeholder="说明处理结果和后续时间" rows={5} maxLength={4000} />
          </label>
          <label>
            <span>内部备注 <small>可选</small></span>
            <textarea value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="只对内部可见" rows={3} maxLength={4000} />
          </label>
          <button className="resolution-submit" type="submit" disabled={!action.trim() || !reply.trim() || saving}>
            {saving ? <RefreshCw className="is-spinning" size={16} /> : <Check size={16} />}
            确认解决并回复
          </button>
        </form>
      </aside>
    );
  }

  return (
    <aside className={`agent-context ${mobileOpen ? "is-mobile-open" : ""}`} aria-label="接管上下文">
      <div className="context-title">
        <div><strong>接管上下文</strong><span>由 Agent 随任务一并提交</span></div>
        <button className="context-mobile-close" type="button" aria-label="关闭接管上下文" onClick={onMobileClose}><X size={17} /></button>
      </div>

      <section className="context-section">
        <h3><ShieldAlert size={14} /> 转接判断</h3>
        <dl>
          <div><dt>原因</dt><dd>{reasonLabels[handoff.reason_code] || handoff.reason_code}</dd></div>
          <div><dt>等待</dt><dd>{formatWait(handoff.requested_at)}</dd></div>
          <div><dt>渠道</dt><dd>Web 客户端</dd></div>
        </dl>
      </section>

      <section className="context-section">
        <h3><MessageSquareText size={14} /> Agent 摘要</h3>
        <p>{handoff.agent_summary}</p>
      </section>

      <section className="context-section">
        <h3><Tag size={14} /> 业务线索</h3>
        {orderId ? <div className="context-data"><span>订单号</span><strong>{orderId}</strong></div> : <p className="context-empty">未识别到订单号</p>}
        {gap && <p className="context-note">知识缺失判断：{gap.is_knowledge_gap ? "建议补充" : "无需补充"}</p>}
      </section>

      <section className="context-section context-trace">
        <h3><RefreshCw size={14} /> Agent 查询轨迹</h3>
        {toolEvents.length ? toolEvents.map((raw, index) => {
          const event = getObject(raw) || {};
          return (
            <div className="trace-row" key={`${String(event.service_name)}-${index}`}>
              <span />
              <div><strong>{String(event.service_name || "service")}</strong><small>{event.status === "failed" ? "调用失败" : "已完成"}</small></div>
            </div>
          );
        }) : <p className="context-empty">本次转接没有额外查询记录</p>}
      </section>
    </aside>
  );
}

function AgentApp() {
  const [filter, setFilter] = useState<FilterId>("open");
  const [query, setQuery] = useState("");
  const [handoffs, setHandoffs] = useState<HandoffSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<HandoffDetail | null>(null);
  const [loadingQueue, setLoadingQueue] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [resolving, setResolving] = useState(false);
  const [mobileWorkspace, setMobileWorkspace] = useState(false);
  const [contextOpen, setContextOpen] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  const currentFilter = filters.find((item) => item.id === filter) || filters[0];

  const refreshQueue = useCallback(async (quiet = false) => {
    if (!quiet) setLoadingQueue(true);
    try {
      const items = await listHandoffs([...currentFilter.statuses]);
      setHandoffs(items);
      setSelectedId((current) => current && items.some((item) => item.id === current)
        ? current
        : items[0]?.id || null);
      setError(null);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "人工队列加载失败。" );
    } finally {
      if (!quiet) setLoadingQueue(false);
    }
  }, [currentFilter.statuses]);

  const refreshDetail = useCallback(async (handoffId: string, quiet = false) => {
    if (!quiet) setLoadingDetail(true);
    try {
      setDetail(await getHandoff(handoffId));
      setError(null);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "接管详情加载失败。" );
    } finally {
      if (!quiet) setLoadingDetail(false);
    }
  }, []);

  useEffect(() => {
    void refreshQueue();
    const timer = window.setInterval(() => void refreshQueue(true), 5000);
    return () => window.clearInterval(timer);
  }, [refreshQueue]);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    void refreshDetail(selectedId);
    const timer = window.setInterval(() => void refreshDetail(selectedId, true), 3000);
    return () => window.clearInterval(timer);
  }, [refreshDetail, selectedId]);

  useEffect(() => {
    if (window.innerWidth <= 720 && !mobileWorkspace) return;
    const delay = window.innerWidth <= 720 ? 260 : 0;
    const timer = window.setTimeout(() => {
      const scroller = endRef.current?.closest(".agent-conversation");
      scroller?.scrollTo({ top: scroller.scrollHeight, behavior: "smooth" });
    }, delay);
    return () => window.clearTimeout(timer);
  }, [detail?.messages.length, mobileWorkspace]);

  const visibleHandoffs = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return handoffs;
    return handoffs.filter((item) => [
      item.subject,
      item.customer_id,
      item.latest_message,
      reasonLabels[item.reason_code],
    ].some((value) => value?.toLowerCase().includes(normalized)));
  }, [handoffs, query]);

  function selectHandoff(handoffId: string) {
    setSelectedId(handoffId);
    setResolving(false);
    setContextOpen(false);
    setMobileWorkspace(true);
  }

  async function accept() {
    if (!detail || working) return;
    setWorking(true);
    try {
      setDetail(await acceptHandoff(detail.id, AGENT_ID));
      if (filter === "queued") setFilter("open");
      else await refreshQueue(true);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "接入失败，请刷新队列后重试。" );
    } finally {
      setWorking(false);
    }
  }

  async function sendReply() {
    const content = draft.trim();
    if (!detail || detail.status !== "active" || !content || working) return;
    setWorking(true);
    try {
      const message = await replyToCustomer({
        handoffId: detail.id,
        agentId: AGENT_ID,
        content,
      });
      setDraft("");
      setDetail((current) => current ? { ...current, messages: [...current.messages, message] } : current);
      await refreshQueue(true);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "回复发送失败。" );
    } finally {
      setWorking(false);
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void sendReply();
    }
  }

  async function completeResolution(payload: { action: string; reply: string; notes: string }) {
    if (!detail) return;
    try {
      const resolved = await resolveHandoff({
        handoffId: detail.id,
        agentId: AGENT_ID,
        resolutionCode: "resolved",
        actionTaken: payload.action,
        replyToCustomer: payload.reply,
        internalNotes: payload.notes,
      });
      setDetail(resolved);
      setResolving(false);
      setContextOpen(false);
      setFilter("resolved");
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "完成服务失败。" );
    }
  }

  return (
    <div className={`agent-app ${mobileWorkspace ? "is-workspace-open" : ""}`}>
      <aside className="agent-rail">
        <a className="agent-logo" href="/agent" aria-label="ServiceLoop 客服工作台">SL</a>
        <nav aria-label="客服工作台导航">
          <a className="is-active" href="/agent" aria-label="人工队列"><Inbox size={19} /></a>
          <a href="/customer" aria-label="打开客户页面"><MessageSquareText size={19} /></a>
        </nav>
        <div className="agent-identity" title="客服 小吴">吴</div>
      </aside>

      <section className="agent-queue" aria-label="人工接管队列">
        <header className="queue-header">
          <div><h1>人工队列</h1><span>{handoffs.length.toString().padStart(2, "0")} 个任务</span></div>
          <button type="button" aria-label="刷新队列" onClick={() => void refreshQueue()}><RefreshCw className={loadingQueue ? "is-spinning" : ""} size={17} /></button>
        </header>

        <div className="queue-filters" role="tablist" aria-label="任务状态">
          {filters.map((item) => (
            <button className={filter === item.id ? "is-active" : ""} key={item.id} type="button" role="tab" aria-selected={filter === item.id} onClick={() => setFilter(item.id)}>
              {item.label}
            </button>
          ))}
        </div>

        <label className="queue-search">
          <Search size={15} />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索客户、问题或原因" />
        </label>

        <div className="queue-list">
          {loadingQueue && handoffs.length === 0 ? (
            <div className="queue-state"><RefreshCw className="is-spinning" size={18} /><span>正在读取接管队列</span></div>
          ) : visibleHandoffs.length === 0 ? (
            <div className="queue-state"><CheckCircle2 size={20} /><strong>当前队列已清空</strong><span>新的转接任务会自动出现在这里。</span></div>
          ) : visibleHandoffs.map((handoff) => (
            <button className={`queue-item ${selectedId === handoff.id ? "is-active" : ""}`} key={handoff.id} type="button" onClick={() => selectHandoff(handoff.id)}>
              <span className={`queue-item__status is-${handoff.status}`} />
              <span className="queue-item__main">
                <span className="queue-item__top"><strong>{handoff.subject || "未命名服务"}</strong><time>{formatClock(handoff.updated_at)}</time></span>
                <span className="queue-item__preview">{handoff.latest_message}</span>
                <span className="queue-item__meta"><b>{reasonLabels[handoff.reason_code] || handoff.reason_code}</b><i>{handoff.status === "queued" ? `已等待 ${formatWait(handoff.requested_at)}` : statusLabels[handoff.status]}</i></span>
              </span>
            </button>
          ))}
        </div>
      </section>

      <main className="agent-workspace">
        {error && <div className="agent-error" role="alert"><X size={15} /><span>{error}</span><button type="button" onClick={() => setError(null)}>关闭</button></div>}
        {!selectedId ? (
          <div className="workspace-empty"><Headphones size={28} /><h2>选择一条接管任务</h2><p>客户问题、Agent 判断和查询轨迹会在同一个工作区展开。</p></div>
        ) : loadingDetail && !detail ? (
          <div className="workspace-empty"><RefreshCw className="is-spinning" size={23} /><p>正在准备接管上下文</p></div>
        ) : detail ? (
          <>
            <header className="workspace-header">
              <button className="workspace-back" type="button" aria-label="返回队列" onClick={() => setMobileWorkspace(false)}><ArrowLeft size={19} /></button>
              <div className="workspace-customer">
                <div className="customer-avatar">林</div>
                <div><h2>{detail.subject || "客户服务"}</h2><span>{detail.customer_id} · Web 客户</span></div>
              </div>
              <div className={`workspace-status is-${detail.status}`}><span />{statusLabels[detail.status]}</div>
              {detail.status === "queued" && (
                <button className="accept-button" type="button" disabled={working} onClick={() => void accept()}>
                  {working ? <RefreshCw className="is-spinning" size={16} /> : <Headphones size={16} />}
                  接入会话
                </button>
              )}
              {detail.status === "active" && (
                <button className="resolve-button" type="button" onClick={() => { setResolving(true); setContextOpen(true); }}><Check size={16} /> 完成服务</button>
              )}
              <button className="workspace-context-button" type="button" aria-label="查看接管上下文" aria-expanded={contextOpen} onClick={() => setContextOpen(!contextOpen)}><PanelRightOpen size={17} /></button>
            </header>

            <div className="workspace-body">
              <section className="agent-conversation" aria-label="客户会话">
                <div className="conversation-day"><span>本次服务记录</span><time>{new Intl.DateTimeFormat("zh-CN", { month: "long", day: "numeric" }).format(new Date(detail.requested_at))}</time></div>
                <div className="handoff-marker"><span><Headphones size={14} /></span><p>AI 已将会话和查询上下文转入人工队列</p></div>
                {detail.messages.map((message) => <MessageRow key={message.id} message={message} />)}
                <div ref={endRef} />
              </section>
              <ContextPanel
                handoff={detail}
                resolving={resolving}
                mobileOpen={contextOpen}
                onMobileClose={() => setContextOpen(false)}
                onCloseResolution={() => { setResolving(false); setContextOpen(false); }}
                onResolve={completeResolution}
              />
            </div>

            <footer className="agent-composer-area">
              {detail.status === "queued" ? (
                <button className="accept-gate" type="button" onClick={() => void accept()} disabled={working}>
                  <Headphones size={17} /><span><strong>接入后即可回复客户</strong><small>接管上下文已经准备完成</small></span><ChevronRight size={17} />
                </button>
              ) : detail.status === "resolved" ? (
                <div className="resolved-gate"><CheckCircle2 size={18} /><span><strong>本次服务已解决</strong><small>处理结论已写入人工服务记录</small></span></div>
              ) : detail.status === "active" ? (
                <div className="agent-composer">
                  <textarea value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={handleKeyDown} aria-label="回复客户" placeholder="回复客户，Enter 发送…" rows={2} maxLength={4000} disabled={working} />
                  <div><span>Shift + Enter 换行</span><button type="button" aria-label="发送回复" onClick={() => void sendReply()} disabled={!draft.trim() || working}><Send size={17} /></button></div>
                </div>
              ) : (
                <div className="assigned-gate"><Clock3 size={18} /><span><strong>等待已分配客服接入</strong><small>接入完成前暂不能发送消息</small></span></div>
              )}
            </footer>
          </>
        ) : null}
      </main>
    </div>
  );
}

export default AgentApp;
