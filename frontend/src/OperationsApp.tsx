import {
  Archive,
  Activity,
  ArrowUpRight,
  BookOpenText,
  Bot,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleAlert,
  Database,
  FileEdit,
  FilePlus2,
  Headphones,
  Inbox,
  LibraryBig,
  ListChecks,
  LoaderCircle,
  MessageSquareText,
  Plus,
  RefreshCw,
  Save,
  Search,
  ShieldCheck,
  Workflow,
  X,
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  archiveKnowledgeDocument,
  createKnowledgeDocument,
  dismissKnowledgeGap,
  getDataOperationsOverview,
  getOperationsOverview,
  listKnowledgeDocuments,
  listKnowledgeDrafts,
  listKnowledgeGaps,
  listKnowledgeVersions,
  listBadCases,
  listDataOperationsRuns,
  listImprovementTasks,
  promoteImprovementTask,
  publishKnowledgeDraft,
  runKnowledgeAgent,
  runDataOperationsAgent,
  resolveImprovementTask,
  updateKnowledgeDocument,
  updateKnowledgeDraft,
} from "./lib/api";
import type {
  BadCase,
  DataOperationsOverview,
  DataOperationsRun,
  ImprovementTask,
  KnowledgeDocument,
  KnowledgeDraft,
  KnowledgeGap,
  KnowledgeVersion,
  OperationsOverview,
} from "./types";

type OperationsView = "gaps" | "drafts" | "documents" | "data";

const reasonLabels: Record<string, string> = {
  low_knowledge_relevance: "检索相关性不足",
  knowledge_not_found: "未检索到知识",
  knowledge_insufficient: "知识不足",
  policy_unclear: "规则不明确",
};

const viewMeta: Record<OperationsView, { title: string; description: string }> = {
  gaps: {
    title: "待补知识",
    description: "检查转人工证据，选择需要由 Agent 归纳的知识缺口。",
  },
  drafts: {
    title: "Agent 草稿",
    description: "核对事实、编辑内容，然后发布到当前检索索引。",
  },
  documents: {
    title: "知识库",
    description: "维护已发布知识、查看版本，并控制检索中的生效状态。",
  },
  data: {
    title: "数据飞轮",
    description: "把低评分、工具失败和异常转人工整理成可验证的改进任务。",
  },
};

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

function getBestScore(gap: KnowledgeGap): number | null {
  const searches = gap.evidence.knowledge_searches;
  if (!Array.isArray(searches)) return null;
  const scores = searches
    .map((item) => item && typeof item === "object" ? (item as Record<string, unknown>).best_rerank_score : null)
    .filter((value): value is number => typeof value === "number");
  return scores.length ? Math.max(...scores) : null;
}

function OperationsRail() {
  return (
    <aside className="ops-rail" aria-label="ServiceLoop 主导航">
      <a className="ops-logo" href="/customer" aria-label="返回 ServiceLoop 客户端">SL</a>
      <nav>
        <a href="/customer" aria-label="客户咨询"><MessageSquareText size={19} /></a>
        <a href="/agent" aria-label="人工客服工作台"><Headphones size={19} /></a>
        <a className="is-active" href="/operations" aria-label="知识运营后台"><LibraryBig size={19} /></a>
      </nav>
      <div className="ops-identity" aria-label="当前运营人员">OP</div>
    </aside>
  );
}

function LoadingRows() {
  return (
    <div className="ops-skeleton" aria-label="正在加载">
      {[0, 1, 2, 3].map((item) => <span key={item} />)}
    </div>
  );
}

export default function OperationsApp() {
  const [view, setView] = useState<OperationsView>("gaps");
  const [overview, setOverview] = useState<OperationsOverview | null>(null);
  const [gaps, setGaps] = useState<KnowledgeGap[]>([]);
  const [drafts, setDrafts] = useState<KnowledgeDraft[]>([]);
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [dataOverview, setDataOverview] = useState<DataOperationsOverview | null>(null);
  const [badCases, setBadCases] = useState<BadCase[]>([]);
  const [improvementTasks, setImprovementTasks] = useState<ImprovementTask[]>([]);
  const [dataRuns, setDataRuns] = useState<DataOperationsRun[]>([]);
  const [selectedGapId, setSelectedGapId] = useState<string | null>(null);
  const [selectedGapIds, setSelectedGapIds] = useState<Set<string>>(new Set());
  const [selectedDraftId, setSelectedDraftId] = useState<string | null>(null);
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | "new" | null>(null);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [versions, setVersions] = useState<KnowledgeVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const selectedGap = useMemo(
    () => gaps.find((item) => item.id === selectedGapId) || null,
    [gaps, selectedGapId],
  );
  const selectedDraft = useMemo(
    () => drafts.find((item) => item.id === selectedDraftId) || null,
    [drafts, selectedDraftId],
  );
  const selectedDocument = useMemo(
    () => documents.find((item) => item.id === selectedDocumentId) || null,
    [documents, selectedDocumentId],
  );
  const selectedTask = useMemo(
    () => improvementTasks.find((item) => item.id === selectedTaskId) || null,
    [improvementTasks, selectedTaskId],
  );

  const loadAll = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true);
    setError(null);
    try {
      const [
        nextOverview,
        nextGaps,
        nextDrafts,
        nextDocuments,
        nextDataOverview,
        nextBadCases,
        nextTasks,
        nextRuns,
      ] = await Promise.all([
        getOperationsOverview(),
        listKnowledgeGaps(),
        listKnowledgeDrafts(),
        listKnowledgeDocuments(),
        getDataOperationsOverview(),
        listBadCases(),
        listImprovementTasks(),
        listDataOperationsRuns(),
      ]);
      setOverview(nextOverview);
      setGaps(nextGaps);
      setDrafts(nextDrafts);
      setDocuments(nextDocuments);
      setDataOverview(nextDataOverview);
      setBadCases(nextBadCases);
      setImprovementTasks(nextTasks);
      setDataRuns(nextRuns);
      setSelectedGapId((current) => current && nextGaps.some((item) => item.id === current)
        ? current
        : nextGaps[0]?.id || null);
      setSelectedDraftId((current) => current && nextDrafts.some((item) => item.id === current)
        ? current
        : nextDrafts[0]?.id || null);
      setSelectedDocumentId((current) => current === "new" || (current && nextDocuments.some((item) => item.id === current))
        ? current
        : nextDocuments[0]?.id || null);
      setSelectedTaskId((current) => current && nextTasks.some((item) => item.id === current)
        ? current
        : nextTasks[0]?.id || null);
      setSelectedGapIds((current) => new Set([...current].filter((id) => nextGaps.some((gap) => gap.id === id))));
    } catch (loadError) {
      setError(loadError instanceof ApiError ? loadError.message : "运营数据加载失败，请稍后重试。");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void loadAll(); }, [loadAll]);

  useEffect(() => {
    if (!selectedDocument || selectedDocumentId === "new") {
      setVersions([]);
      return;
    }
    void listKnowledgeVersions(selectedDocument.id)
      .then(setVersions)
      .catch(() => setVersions([]));
  }, [selectedDocument, selectedDocumentId]);

  function showNotice(message: string) {
    setNotice(message);
    window.setTimeout(() => setNotice(null), 3200);
  }

  function toggleGap(gapId: string) {
    setSelectedGapIds((current) => {
      const next = new Set(current);
      if (next.has(gapId)) next.delete(gapId);
      else next.add(gapId);
      return next;
    });
  }

  async function generateDrafts() {
    const gapIds = selectedGapIds.size ? [...selectedGapIds] : gaps.map((item) => item.id);
    if (!gapIds.length || working) return;
    setWorking("agent");
    setError(null);
    try {
      const result = await runKnowledgeAgent(gapIds);
      showNotice(result.message);
      await loadAll(true);
      if (result.drafts[0]) setSelectedDraftId(result.drafts[0].id);
      setSelectedGapIds(new Set());
      setView("drafts");
    } catch (runError) {
      setError(runError instanceof ApiError ? runError.message : "知识 Agent 运行失败。");
    } finally {
      setWorking(null);
    }
  }

  async function dismissGap(gapId: string) {
    if (working) return;
    setWorking(`dismiss-${gapId}`);
    try {
      await dismissKnowledgeGap(gapId);
      showNotice("该缺口已标记为无需补充。");
      await loadAll(true);
    } catch (dismissError) {
      setError(dismissError instanceof ApiError ? dismissError.message : "无法更新知识缺口。");
    } finally {
      setWorking(null);
    }
  }

  const navigation = [
    { id: "gaps" as const, label: "待补知识", icon: Inbox, count: overview?.pending_gaps ?? gaps.length },
    { id: "drafts" as const, label: "Agent 草稿", icon: FileEdit, count: overview?.open_drafts ?? drafts.filter((item) => item.status === "draft").length },
    { id: "documents" as const, label: "知识库", icon: BookOpenText, count: overview?.published_documents ?? documents.filter((item) => item.status === "published").length },
    { id: "data" as const, label: "数据飞轮", icon: Workflow, count: dataOverview?.open_improvement_tasks ?? improvementTasks.filter((item) => item.status === "open").length },
  ];

  return (
    <div className="ops-app">
      <OperationsRail />
      <aside className="ops-sidebar">
        <header>
          <div><strong>运营中心</strong><span>Knowledge operations</span></div>
          <ShieldCheck size={18} aria-hidden="true" />
        </header>
        <nav aria-label="知识运营功能">
          {navigation.map((item) => {
            const Icon = item.icon;
            return (
              <button
                className={view === item.id ? "is-active" : ""}
                type="button"
                key={item.id}
                onClick={() => setView(item.id)}
              >
                <Icon size={17} />
                <span>{item.label}</span>
                <b>{item.count}</b>
                <ChevronRight size={14} />
              </button>
            );
          })}
        </nav>
        <div className="ops-index-state">
          <span className={overview?.index.ready ? "is-ready" : ""} />
          <div>
            <strong>{overview?.index.ready ? "检索索引已就绪" : "知识库等待内容"}</strong>
            <small>
              {overview?.index.chunk_count ?? 0} 个知识块 · v{overview?.index.index_version ?? 0}
            </small>
          </div>
        </div>
        <footer><span>OP</span><div><strong>演示运营人员</strong><small>可直接发布知识</small></div></footer>
      </aside>

      <main className="ops-main">
        <header className="ops-main-header">
          <div>
            <h1>{viewMeta[view].title}</h1>
            <p>{viewMeta[view].description}</p>
          </div>
          <button type="button" onClick={() => void loadAll()} disabled={loading}>
            <RefreshCw className={loading ? "is-spinning" : ""} size={16} />
            <span>刷新</span>
          </button>
        </header>

        <dl className="ops-ledger-strip">
          {view === "data" ? (
            <>
              <div><dt>客户反馈</dt><dd>{dataOverview?.feedback_total ?? "—"}</dd></div>
              <div><dt>低评分</dt><dd>{dataOverview?.negative_feedback ?? "—"}</dd></div>
              <div><dt>工具失败</dt><dd>{dataOverview?.failed_tool_calls ?? "—"}</dd></div>
              <div><dt>开放改进</dt><dd>{dataOverview?.open_improvement_tasks ?? "—"}</dd></div>
            </>
          ) : (
            <>
              <div><dt>待处理缺口</dt><dd>{overview?.pending_gaps ?? "—"}</dd></div>
              <div><dt>开放草稿</dt><dd>{overview?.open_drafts ?? "—"}</dd></div>
              <div><dt>已发布知识</dt><dd>{overview?.published_documents ?? "—"}</dd></div>
              <div><dt>当前索引</dt><dd>{overview?.index.ready ? "可检索" : "空"}</dd></div>
            </>
          )}
        </dl>

        {error && (
          <div className="ops-error" role="alert">
            <CircleAlert size={16} /><span>{error}</span>
            <button type="button" aria-label="关闭错误提示" onClick={() => setError(null)}><X size={15} /></button>
          </div>
        )}
        {notice && <div className="ops-notice" role="status"><CheckCircle2 size={16} />{notice}</div>}

        {loading ? <LoadingRows /> : view === "gaps" ? (
          <GapsWorkspace
            gaps={gaps}
            selectedGap={selectedGap}
            selectedIds={selectedGapIds}
            running={working === "agent"}
            dismissing={Boolean(working?.startsWith("dismiss-"))}
            onSelectGap={setSelectedGapId}
            onToggleGap={toggleGap}
            onToggleAll={() => setSelectedGapIds(
              selectedGapIds.size === gaps.length ? new Set() : new Set(gaps.map((item) => item.id)),
            )}
            onGenerate={() => void generateDrafts()}
            onDismiss={(gapId) => void dismissGap(gapId)}
          />
        ) : view === "drafts" ? (
          <DraftsWorkspace
            drafts={drafts}
            selected={selectedDraft}
            working={working}
            onSelect={setSelectedDraftId}
            onWorking={setWorking}
            onError={setError}
            onSaved={async (message) => { showNotice(message); await loadAll(true); }}
            onPublished={async () => {
              showNotice("知识已发布并进入当前检索索引。");
              await loadAll(true);
              setView("documents");
            }}
          />
        ) : view === "documents" ? (
          <DocumentsWorkspace
            documents={documents}
            selected={selectedDocument}
            selectedId={selectedDocumentId}
            versions={versions}
            working={working}
            onSelect={setSelectedDocumentId}
            onWorking={setWorking}
            onError={setError}
            onSaved={async (document, message) => {
              setSelectedDocumentId(document.id);
              showNotice(message);
              await loadAll(true);
            }}
          />
        ) : (
          <DataFlywheelWorkspace
            overview={dataOverview}
            badCases={badCases}
            tasks={improvementTasks}
            runs={dataRuns}
            selected={selectedTask}
            working={working}
            onSelect={setSelectedTaskId}
            onWorking={setWorking}
            onError={setError}
            onRun={async () => {
              setWorking("data-agent");
              setError(null);
              try {
                const result = await runDataOperationsAgent();
                showNotice(result.run.summary);
                await loadAll(true);
                if (result.improvement_tasks[0]) {
                  setSelectedTaskId(result.improvement_tasks[0].id);
                }
              } catch (runError) {
                setError(runError instanceof ApiError ? runError.message : "数据运营 Agent 运行失败。");
              } finally {
                setWorking(null);
              }
            }}
            onChanged={async (message) => {
              showNotice(message);
              await loadAll(true);
            }}
          />
        )}
      </main>
    </div>
  );
}

function GapsWorkspace({
  gaps,
  selectedGap,
  selectedIds,
  running,
  dismissing,
  onSelectGap,
  onToggleGap,
  onToggleAll,
  onGenerate,
  onDismiss,
}: {
  gaps: KnowledgeGap[];
  selectedGap: KnowledgeGap | null;
  selectedIds: Set<string>;
  running: boolean;
  dismissing: boolean;
  onSelectGap: (id: string) => void;
  onToggleGap: (id: string) => void;
  onToggleAll: () => void;
  onGenerate: () => void;
  onDismiss: (id: string) => void;
}) {
  const [detailOpen, setDetailOpen] = useState(false);

  function selectGap(gapId: string) {
    onSelectGap(gapId);
    setDetailOpen(true);
  }

  return (
    <section className="ops-workspace ops-gaps-workspace">
      <div className="ops-list-panel">
        <div className="ops-toolbar">
          <label><input type="checkbox" checked={gaps.length > 0 && selectedIds.size === gaps.length} onChange={onToggleAll} />选择全部</label>
          <button className="ops-primary-action" type="button" disabled={!gaps.length || running} onClick={onGenerate}>
            {running ? <LoaderCircle className="is-spinning" size={16} /> : <Bot size={16} />}
            {running ? "正在归纳证据" : `生成草稿${selectedIds.size ? ` · ${selectedIds.size}` : ""}`}
          </button>
        </div>
        {gaps.length ? (
          <div className="ops-gap-list">
            <div className="ops-table-head"><span>选择</span><span>客户问题</span><span>转接原因</span><span>相关性</span><span>时间</span></div>
            {gaps.map((gap) => {
              const score = getBestScore(gap);
              return (
                <div className={`ops-gap-row ${selectedGap?.id === gap.id ? "is-active" : ""}`} key={gap.id}>
                  <label aria-label={`选择 ${gap.question}`}><input type="checkbox" checked={selectedIds.has(gap.id)} onChange={() => onToggleGap(gap.id)} /></label>
                  <button type="button" onClick={() => selectGap(gap.id)}><strong>{gap.question}</strong><small>{gap.conversation_id || "无关联会话"}</small></button>
                  <span>{reasonLabels[gap.reason] || gap.reason}</span>
                  <span className={score !== null && score < .35 ? "is-low" : ""}>{score === null ? "无结果" : score.toFixed(2)}</span>
                  <time>{formatDate(gap.created_at)}</time>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="ops-empty"><CheckCircle2 size={25} /><strong>没有待补知识</strong><p>新的知识缺口会在客服 Agent 转人工后自动进入这里。</p></div>
        )}
      </div>
      <aside className={`ops-detail-panel ${detailOpen ? "is-open" : ""}`}>
        {selectedGap ? (
          <>
            <header>
              <span>缺口证据</span>
              <div>
                <b>{reasonLabels[selectedGap.reason] || selectedGap.reason}</b>
                <button className="ops-detail-close" type="button" aria-label="关闭缺口证据" onClick={() => setDetailOpen(false)}><X size={15} /></button>
              </div>
            </header>
            <h2>{selectedGap.question}</h2>
            <dl>
              <div><dt>关联会话</dt><dd>{selectedGap.conversation_id || "—"}</dd></div>
              <div><dt>最佳 ReRank</dt><dd>{getBestScore(selectedGap)?.toFixed(2) || "未命中"}</dd></div>
              <div><dt>当前状态</dt><dd>等待归纳</dd></div>
            </dl>
            <section>
              <h3>人工处理结论</h3>
              {selectedGap.human_resolution ? (
                <blockquote>{selectedGap.human_resolution.reply_to_customer}</blockquote>
              ) : <p className="ops-pending-copy">人工会话尚未形成最终结论，Agent 草稿会标记待确认内容。</p>}
            </section>
            <section>
              <h3>Agent 将如何处理</h3>
              <ol><li>按问题相似度归组</li><li>只读取检索证据与人工结论</li><li>证据不足时保留待确认标记</li></ol>
            </section>
            <button className="ops-text-action" type="button" disabled={dismissing} onClick={() => onDismiss(selectedGap.id)}>无需补充此知识</button>
          </>
        ) : <div className="ops-empty"><Search size={23} /><strong>选择一条缺口</strong><p>右侧会展示转人工证据和人工处理结论。</p></div>}
      </aside>
    </section>
  );
}

function DraftsWorkspace({
  drafts,
  selected,
  working,
  onSelect,
  onWorking,
  onError,
  onSaved,
  onPublished,
}: {
  drafts: KnowledgeDraft[];
  selected: KnowledgeDraft | null;
  working: string | null;
  onSelect: (id: string) => void;
  onWorking: (value: string | null) => void;
  onError: (value: string | null) => void;
  onSaved: (message: string) => Promise<void>;
  onPublished: () => Promise<void>;
}) {
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  useEffect(() => { setTitle(selected?.title || ""); setContent(selected?.content || ""); }, [selected]);

  async function save() {
    if (!selected || selected.status !== "draft" || !title.trim() || !content.trim()) return;
    onWorking("save-draft");
    onError(null);
    try {
      await updateKnowledgeDraft(selected.id, { title: title.trim(), content: content.trim() });
      await onSaved("草稿修改已保存。");
    } catch (saveError) {
      onError(saveError instanceof ApiError ? saveError.message : "草稿保存失败。");
    } finally { onWorking(null); }
  }

  async function publish() {
    if (!selected || selected.status !== "draft") return;
    onWorking("publish-draft");
    onError(null);
    try {
      if (title !== selected.title || content !== selected.content) {
        await updateKnowledgeDraft(selected.id, { title: title.trim(), content: content.trim() });
      }
      await publishKnowledgeDraft(selected.id);
      await onPublished();
    } catch (publishError) {
      onError(publishError instanceof ApiError ? publishError.message : "知识发布失败。");
    } finally { onWorking(null); }
  }

  return (
    <section className="ops-workspace ops-editor-workspace">
      <aside className="ops-record-list">
        <header><strong>全部草稿</strong><span>{drafts.length}</span></header>
        {drafts.length ? drafts.map((draft) => (
          <button className={selected?.id === draft.id ? "is-active" : ""} type="button" key={draft.id} onClick={() => onSelect(draft.id)}>
            <span className={`ops-record-status is-${draft.status}`} />
            <span><strong>{draft.title}</strong><small>{draft.gap_ids.length} 条缺口 · {formatDate(draft.updated_at)}</small></span>
            <b>{draft.status === "draft" ? "待发布" : "已发布"}</b>
          </button>
        )) : <div className="ops-empty"><FileEdit size={23} /><strong>还没有草稿</strong><p>从“待补知识”选择缺口并运行 Agent。</p></div>}
      </aside>
      <div className="ops-editor-panel">
        {selected ? (
          <>
            <header>
              <div><strong>{selected.status === "draft" ? "编辑知识草稿" : "已发布草稿"}</strong><span>来源：{selected.generated_by}</span></div>
              <span className={`ops-state-label is-${selected.status}`}>{selected.status === "draft" ? "等待发布" : "已进入知识库"}</span>
            </header>
            <label className="ops-field"><span>知识标题</span><input value={title} disabled={selected.status !== "draft"} maxLength={255} onChange={(event) => setTitle(event.target.value)} /></label>
            <label className="ops-field ops-field--content"><span>知识正文</span><textarea value={content} disabled={selected.status !== "draft"} onChange={(event) => setContent(event.target.value)} /></label>
            <div className="ops-draft-footnote"><Bot size={15} /><span>{selected.generation_notes || "Agent 只使用缺口证据生成，发布前请核对事实。"}</span></div>
            <footer>
              <span>{content.trim().length} 字 · 关联 {selected.gap_ids.length} 条缺口</span>
              {selected.status === "draft" && <>
                <button type="button" disabled={Boolean(working) || !title.trim() || !content.trim()} onClick={() => void save()}><Save size={16} />保存修改</button>
                <button className="ops-primary-action" type="button" disabled={Boolean(working) || !title.trim() || !content.trim()} onClick={() => void publish()}>
                  {working === "publish-draft" ? <LoaderCircle className="is-spinning" size={16} /> : <Check size={16} />}确认并发布
                </button>
              </>}
            </footer>
          </>
        ) : <div className="ops-empty"><FileEdit size={25} /><strong>选择一份草稿</strong><p>在这里编辑 Agent 生成的内容并发布。</p></div>}
      </div>
    </section>
  );
}

function DocumentsWorkspace({
  documents,
  selected,
  selectedId,
  versions,
  working,
  onSelect,
  onWorking,
  onError,
  onSaved,
}: {
  documents: KnowledgeDocument[];
  selected: KnowledgeDocument | null;
  selectedId: string | "new" | null;
  versions: KnowledgeVersion[];
  working: string | null;
  onSelect: (id: string | "new") => void;
  onWorking: (value: string | null) => void;
  onError: (value: string | null) => void;
  onSaved: (document: KnowledgeDocument, message: string) => Promise<void>;
}) {
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [confirmArchive, setConfirmArchive] = useState(false);
  useEffect(() => {
    setTitle(selectedId === "new" ? "" : selected?.title || "");
    setContent(selectedId === "new" ? "" : selected?.content || "");
    setConfirmArchive(false);
  }, [selected, selectedId]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!title.trim() || !content.trim() || working) return;
    onWorking("save-document");
    onError(null);
    try {
      const document = selectedId === "new"
        ? await createKnowledgeDocument({ title: title.trim(), content: content.trim() })
        : await updateKnowledgeDocument(String(selectedId), { title: title.trim(), content: content.trim() });
      await onSaved(document, selectedId === "new" ? "知识已发布并可检索。" : `已发布版本 ${document.current_version}。`);
    } catch (saveError) {
      onError(saveError instanceof ApiError ? saveError.message : "知识保存失败。");
    } finally { onWorking(null); }
  }

  async function archive() {
    if (!selected || working) return;
    onWorking("archive-document");
    try {
      const document = await archiveKnowledgeDocument(selected.id);
      await onSaved(document, "知识已停用，并从检索索引移除。");
    } catch (archiveError) {
      onError(archiveError instanceof ApiError ? archiveError.message : "知识停用失败。");
    } finally { onWorking(null); setConfirmArchive(false); }
  }

  return (
    <section className="ops-workspace ops-editor-workspace">
      <aside className="ops-record-list">
        <header><strong>知识文档</strong><button type="button" onClick={() => onSelect("new")}><Plus size={15} />新增</button></header>
        {documents.length ? documents.map((document) => (
          <button className={selected?.id === document.id && selectedId !== "new" ? "is-active" : ""} type="button" key={document.id} onClick={() => onSelect(document.id)}>
            <span className={`ops-record-status is-${document.status}`} />
            <span><strong>{document.title}</strong><small>版本 {document.current_version} · {formatDate(document.updated_at)}</small></span>
            <b>{document.status === "published" ? "生效" : "停用"}</b>
          </button>
        )) : <div className="ops-empty"><Database size={23} /><strong>知识库还是空的</strong><p>新增第一篇知识，或从 Agent 草稿发布。</p></div>}
      </aside>
      <form className="ops-editor-panel" onSubmit={submit}>
        {selected || selectedId === "new" ? (
          <>
            <header>
              <div><strong>{selectedId === "new" ? "新增知识" : "编辑已发布知识"}</strong><span>{selectedId === "new" ? "保存后立即进入检索" : `文档 ${selected?.id}`}</span></div>
              {selected && <span className={`ops-state-label is-${selected.status}`}>{selected.status === "published" ? "当前生效" : "已停用"}</span>}
            </header>
            <label className="ops-field"><span>知识标题</span><input value={title} maxLength={255} placeholder="例如：X3 智能手表退货条件" onChange={(event) => setTitle(event.target.value)} /></label>
            <label className="ops-field ops-field--content"><span>知识正文</span><textarea value={content} placeholder="写清适用范围、处理规则与例外条件…" onChange={(event) => setContent(event.target.value)} /></label>
            {selected && versions.length > 0 && (
              <div className="ops-version-line"><span>版本记录</span>{versions.slice(0, 4).map((version) => <b key={version.id}>v{version.version} · {formatDate(version.published_at)}</b>)}</div>
            )}
            {confirmArchive && selected ? (
              <div className="ops-archive-confirm"><Archive size={16} /><span>停用后会从检索索引移除，但版本记录仍保留。</span><button type="button" onClick={() => setConfirmArchive(false)}>取消</button><button type="button" onClick={() => void archive()}>确认停用</button></div>
            ) : null}
            <footer>
              {selected && selected.status === "published" ? <button className="ops-text-action" type="button" onClick={() => setConfirmArchive(true)}><Archive size={15} />停用知识</button> : <span>{content.trim().length} 字</span>}
              <button className="ops-primary-action" type="submit" disabled={Boolean(working) || !title.trim() || !content.trim()}>
                {working === "save-document" ? <LoaderCircle className="is-spinning" size={16} /> : selectedId === "new" ? <FilePlus2 size={16} /> : <Save size={16} />}
                {selectedId === "new" ? "发布知识" : "发布新版本"}
              </button>
            </footer>
          </>
        ) : <div className="ops-empty"><BookOpenText size={25} /><strong>选择一篇知识</strong><p>查看内容、版本和当前检索状态。</p></div>}
      </form>
    </section>
  );
}

const dataCategoryLabels: Record<string, string> = {
  knowledge: "知识缺口",
  tool: "工具可靠性",
  experience: "服务体验",
  process: "处理流程",
};

function DataFlywheelWorkspace({
  overview,
  badCases,
  tasks,
  runs,
  selected,
  working,
  onSelect,
  onWorking,
  onError,
  onRun,
  onChanged,
}: {
  overview: DataOperationsOverview | null;
  badCases: BadCase[];
  tasks: ImprovementTask[];
  runs: DataOperationsRun[];
  selected: ImprovementTask | null;
  working: string | null;
  onSelect: (id: string) => void;
  onWorking: (value: string | null) => void;
  onError: (value: string | null) => void;
  onRun: () => Promise<void>;
  onChanged: (message: string) => Promise<void>;
}) {
  const [resolutionNotes, setResolutionNotes] = useState("");
  useEffect(() => setResolutionNotes(selected?.resolution_notes || ""), [selected]);

  const selectedCases = selected
    ? badCases.filter((item) => selected.bad_case_ids.includes(item.id))
    : [];

  async function promote() {
    if (!selected || working) return;
    onWorking("promote-improvement");
    onError(null);
    try {
      await promoteImprovementTask(selected.id);
      await onChanged("改进任务已回流到“待补知识”，可继续生成知识草稿。");
    } catch (reason) {
      onError(reason instanceof ApiError ? reason.message : "无法回流知识缺口。");
    } finally {
      onWorking(null);
    }
  }

  async function resolve() {
    if (!selected || !resolutionNotes.trim() || working) return;
    onWorking("resolve-improvement");
    onError(null);
    try {
      await resolveImprovementTask(selected.id, resolutionNotes.trim());
      await onChanged("改进任务已完成，关联 Bad Case 同步关闭。");
    } catch (reason) {
      onError(reason instanceof ApiError ? reason.message : "无法完成改进任务。");
    } finally {
      onWorking(null);
    }
  }

  return (
    <section className="ops-workspace ops-data-workspace">
      <div className="ops-flywheel-main">
        <div className="ops-data-toolbar">
          <div>
            <strong>运行信号账本</strong>
            <span>{overview?.open_bad_cases ?? 0} 个待归纳案例 · {tasks.length} 项累计改进任务</span>
          </div>
          <button className="ops-primary-action" type="button" disabled={Boolean(working)} onClick={() => void onRun()}>
            {working === "data-agent" ? <LoaderCircle className="is-spinning" size={16} /> : <Activity size={16} />}
            {working === "data-agent" ? "正在归纳信号" : "运行数据 Agent"}
          </button>
        </div>

        <ol className="ops-flywheel-line" aria-label="数据运营飞轮">
          <li><span>1</span><div><strong>运行信号</strong><small>低评分 · 工具失败 · 异常转接</small></div></li>
          <li><span>2</span><div><strong>Bad Case</strong><small>去重并保留原始证据</small></div></li>
          <li><span>3</span><div><strong>改进任务</strong><small>按知识、工具、体验归组</small></div></li>
          <li><span>4</span><div><strong>回流验证</strong><small>补知识或关闭问题</small></div></li>
        </ol>

        <div className="ops-task-list">
          <header><span>改进任务</span><span>案例</span><span>状态</span><span>更新时间</span></header>
          {tasks.length ? tasks.map((task) => (
            <button className={selected?.id === task.id ? "is-active" : ""} type="button" key={task.id} onClick={() => onSelect(task.id)}>
              <span className={`ops-record-status is-${task.status === "open" ? "draft" : "published"}`} />
              <span><strong>{task.title}</strong><small>{dataCategoryLabels[task.category] || task.category}</small></span>
              <b>{task.bad_case_ids.length}</b>
              <em>{task.status === "open" ? "待处理" : "已完成"}</em>
              <time>{formatDate(task.updated_at)}</time>
            </button>
          )) : (
            <div className="ops-empty"><ListChecks size={24} /><strong>还没有改进任务</strong><p>运行数据 Agent，它会从真实客服信号中生成第一批任务。</p></div>
          )}
        </div>

        {runs[0] && (
          <div className="ops-latest-run">
            <Workflow size={16} />
            <div><strong>最近一次 Agent 运行</strong><span>{runs[0].summary}</span></div>
            <time>{formatDate(runs[0].created_at)}</time>
          </div>
        )}
      </div>

      <aside className="ops-data-detail">
        {selected ? (
          <>
            <header>
              <span>{dataCategoryLabels[selected.category] || selected.category}</span>
              <b className={selected.status === "resolved" ? "is-resolved" : ""}>{selected.status === "open" ? "开放" : "已完成"}</b>
            </header>
            <h2>{selected.title}</h2>
            <p className="ops-task-description">{selected.description}</p>
            <dl>
              <div><dt>关联 Bad Case</dt><dd>{selected.bad_case_ids.length}</dd></div>
              <div><dt>负责人</dt><dd>{selected.owner_id || "待领取"}</dd></div>
              <div><dt>创建时间</dt><dd>{formatDate(selected.created_at)}</dd></div>
            </dl>

            <section className="ops-case-evidence">
              <h3>案例证据</h3>
              {selectedCases.length ? selectedCases.map((badCase) => (
                <article key={badCase.id}>
                  <div><span>{badCase.source_type}</span><b className={`is-${badCase.severity}`}>{badCase.severity === "high" ? "高" : "中"}</b></div>
                  <p>{badCase.summary}</p>
                  <small>{badCase.conversation_id || "无关联会话"}</small>
                </article>
              )) : <p className="ops-pending-copy">案例证据正在载入。</p>}
            </section>

            {selected.linked_knowledge_gap_id && (
              <div className="ops-loop-result"><CheckCircle2 size={16} /><span>已回流待补知识：{selected.linked_knowledge_gap_id}</span></div>
            )}

            {selected.status === "open" ? (
              <div className="ops-task-actions">
                {(selected.category === "knowledge" || selected.category === "experience") && !selected.linked_knowledge_gap_id && (
                  <button type="button" className="ops-promote-action" disabled={Boolean(working)} onClick={() => void promote()}><ArrowUpRight size={15} />转为知识缺口</button>
                )}
                <label><span>处理结论</span><textarea value={resolutionNotes} placeholder="记录修复内容和验证方式…" onChange={(event) => setResolutionNotes(event.target.value)} /></label>
                <button className="ops-primary-action" type="button" disabled={Boolean(working) || !resolutionNotes.trim()} onClick={() => void resolve()}>
                  {working === "resolve-improvement" ? <LoaderCircle className="is-spinning" size={16} /> : <Check size={16} />}完成改进任务
                </button>
              </div>
            ) : (
              <blockquote className="ops-resolution-note">{selected.resolution_notes}</blockquote>
            )}
          </>
        ) : (
          <div className="ops-empty"><Workflow size={25} /><strong>选择一项改进任务</strong><p>查看它来自哪些客服信号，以及应该回流到哪条链路。</p></div>
        )}
      </aside>
    </section>
  );
}
