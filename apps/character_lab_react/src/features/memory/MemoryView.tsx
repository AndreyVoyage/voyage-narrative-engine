import { useCallback, useEffect, useState } from "react";
import { useAppState } from "../../app/AppState";
import { DataTableShell, EmptyState, Inline, Panel, Section, Toolbar } from "../../components/primitives";
import type { DataTableColumn } from "../../components/primitives";
import {
  ALL_CONSOLIDATED_RELATION_KINDS,
  ALL_MEMORY_KINDS,
  type ConsolidatedMemoryRecordSummary,
  type ConsolidatedRelationKind,
  type MemoryEventInspection,
  type MemoryKind,
  type MemoryPromotionCandidateSummary,
} from "../../client/types";

/**
 * Operator Memory view: raw events -> promotion candidates -> consolidated
 * long-term memory, plus standalone record relations. The backend/service is
 * authoritative for eligibility and every validation rule; this view only
 * selects and confirms. Nothing here edits memory text or promotes anything
 * automatically.
 */

const USER_REPORT_NOTE = "Со слов собеседника — не независимо подтверждённый факт";

const PROVENANCE_LABELS: Record<string, string> = {
  USER_STATED: "Сообщил пользователь",
  CHARACTER_UTTERANCE: "Сказал персонаж / модель",
  SCENE_SETUP: "Условие сцены",
  LEGACY_UNCLASSIFIED: "Старая запись — не классифицировано",
};

const INELIGIBLE_LABELS: Record<string, string> = {
  not_a_user_message: "не сообщение пользователя",
  not_user_stated: "не подтверждено пользователем",
  empty_content: "пустое содержимое",
};

const STATUS_LABELS: Record<string, string> = {
  PENDING: "ОЖИДАЕТ",
  APPROVED: "ОДОБРЕНО",
  REJECTED: "ОТКЛОНЕНО",
};

function shortId(id: string): string {
  return id.length > 18 ? id.slice(0, 18) + "…" : id;
}

type MemoryTab = "events" | "candidates" | "consolidated";

const TABS: ReadonlyArray<{ key: MemoryTab; label: string }> = [
  { key: "events", label: "СОБЫТИЯ" },
  { key: "candidates", label: "КАНДИДАТЫ" },
  { key: "consolidated", label: "ДОЛГОВРЕМЕННАЯ" },
];

interface TabProps {
  readonly workspaceId: string;
  readonly tick: number;
}

export function MemoryView() {
  const { state, client } = useAppState();
  const workspaceId = state.selectedWorkspaceId;
  const [tab, setTab] = useState<MemoryTab>("events");
  const [eventsTick, setEventsTick] = useState(0);
  const [candidatesTick, setCandidatesTick] = useState(0);
  const [consolidatedTick, setConsolidatedTick] = useState(0);
  const [promotionSource, setPromotionSource] = useState<MemoryEventInspection | null>(null);
  const [relationFrom, setRelationFrom] = useState<ConsolidatedMemoryRecordSummary | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // Workspace switch: never display prior-workspace selections/dialogs.
  useEffect(() => {
    setPromotionSource(null);
    setRelationFrom(null);
    setActionError(null);
    setEventsTick((t) => t + 1);
    setCandidatesTick((t) => t + 1);
    setConsolidatedTick((t) => t + 1);
  }, [workspaceId]);

  const runAction = useCallback(async (fn: () => Promise<unknown>) => {
    setActionError(null);
    try {
      await fn();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  if (!workspaceId) {
    return (
      <Panel>
        <EmptyState title="Рабочая область ещё не готова" />
      </Panel>
    );
  }

  return (
    <Panel>
      <Toolbar>
        {TABS.map((t) => (
          <button
            key={t.key}
            className="clab-btn"
            data-active={tab === t.key ? "true" : undefined}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
        <span className="clab-form-field__label">Рабочая область: {workspaceId}</span>
      </Toolbar>
      {actionError && (
        <div className="clab-state-error" role="alert">
          {actionError}
        </div>
      )}
      {promotionSource && (
        <PromotionPanel
          source={promotionSource}
          onCancel={() => setPromotionSource(null)}
          onCreate={(kind) =>
            void runAction(async () => {
              await client.proposeMemoryPromotion(workspaceId, promotionSource.eventId, kind);
              setPromotionSource(null);
              setCandidatesTick((t) => t + 1);
            })
          }
        />
      )}
      {relationFrom && (
        <RelationPanel
          workspaceId={workspaceId}
          from={relationFrom}
          tick={consolidatedTick}
          onCancel={() => setRelationFrom(null)}
          onCreate={(targetId, kind) =>
            void runAction(async () => {
              await client.createConsolidatedMemoryRelation(
                workspaceId,
                relationFrom.recordId,
                targetId,
                kind
              );
              setRelationFrom(null);
              setConsolidatedTick((t) => t + 1);
            })
          }
        />
      )}
      {tab === "events" && (
        <EventsTab
          workspaceId={workspaceId}
          tick={eventsTick}
          onPromote={(event) => setPromotionSource(event)}
        />
      )}
      {tab === "candidates" && (
        <CandidatesTab
          workspaceId={workspaceId}
          tick={candidatesTick}
          onDecide={(candidateId, decision) =>
            void runAction(async () => {
              await client.decideMemoryPromotion(workspaceId, candidateId, decision);
              setCandidatesTick((t) => t + 1);
              if (decision === "APPROVE") setConsolidatedTick((t) => t + 1);
            })
          }
        />
      )}
      {tab === "consolidated" && (
        <ConsolidatedTab
          workspaceId={workspaceId}
          tick={consolidatedTick}
          onRelate={(record) => setRelationFrom(record)}
        />
      )}
    </Panel>
  );
}

// --------------------------------------------------------------------- events

interface EventsTabProps extends TabProps {
  readonly onPromote: (event: MemoryEventInspection) => void;
}

function EventsTab({ workspaceId, tick, onPromote }: EventsTabProps) {
  const { client } = useAppState();
  const [events, setEvents] = useState<readonly MemoryEventInspection[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setEvents(null);
    setError(null);
    client
      .listMemoryEvents(workspaceId)
      .then((list) => {
        if (!cancelled) setEvents(list.events);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      });
    return () => {
      cancelled = true;
    };
  }, [client, workspaceId, tick]);

  if (error) return <EmptyState title="Ошибка памяти">Ошибка: {error}</EmptyState>;
  if (!events) return <EmptyState title="Загрузка памяти…" />;

  const columns: readonly DataTableColumn<MemoryEventInspection>[] = [
    { key: "seq", header: "seq", render: (e) => e.seq ?? "—" },
    { key: "type", header: "тип", render: (e) => e.eventType },
    {
      key: "provenance",
      header: "источник",
      render: (e) => PROVENANCE_LABELS[e.provenance] ?? e.provenance,
    },
    { key: "content", header: "содержание", render: (e) => e.meaning, wrap: true },
    { key: "session", header: "сессия", render: (e) => shortId(e.sessionId) },
    {
      key: "eligibility",
      header: "допуск",
      render: (e) =>
        e.eligibleForPromotion ? (
          <span className="clab-badge clab-badge--ok">ELIGIBLE</span>
        ) : (
          <span className="clab-badge clab-badge--warn">
            INELIGIBLE
            {e.ineligibilityReason
              ? ` — ${INELIGIBLE_LABELS[e.ineligibilityReason] ?? e.ineligibilityReason}`
              : ""}
          </span>
        ),
    },
    {
      key: "action",
      header: "",
      render: (e) =>
        e.eligibleForPromotion ? (
          <button className="clab-btn" onClick={() => onPromote(e)}>
            В долгую память
          </button>
        ) : null,
    },
  ];

  return (
    <Section title={`События (порядок: seq) — ${events.length}`}>
      <DataTableShell columns={columns} rows={events} rowKey={(e) => e.eventId} emptyMessage="Память пуста." />
    </Section>
  );
}

// ------------------------------------------------------------------ promotion

interface PromotionPanelProps {
  readonly source: MemoryEventInspection;
  readonly onCancel: () => void;
  readonly onCreate: (kind: MemoryKind) => void;
}

function PromotionPanel({ source, onCancel, onCreate }: PromotionPanelProps) {
  const [kind, setKind] = useState<MemoryKind>("SEMANTIC");
  return (
    <Section title="Новый кандидат в долговременную память">
      <div className="clab-form-field__label">ИСХОДНОЕ СОБЫТИЕ (текст не редактируется):</div>
      <blockquote>{source.meaning}</blockquote>
      <div className="clab-form-field__label">
        ЭПИСТЕМИЧЕСКИЙ ТИП: USER_REPORT — {USER_REPORT_NOTE}
      </div>
      <Inline gap={2}>
        <select
          className="clab-select"
          value={kind}
          onChange={(e) => setKind(e.target.value as MemoryKind)}
        >
          {ALL_MEMORY_KINDS.map((k) => (
            <option key={k} value={k}>
              {k}
            </option>
          ))}
        </select>
        <button className="clab-btn clab-btn--primary" onClick={() => onCreate(kind)}>
          Создать кандидата
        </button>
        <button className="clab-btn" onClick={onCancel}>
          Отмена
        </button>
      </Inline>
    </Section>
  );
}

// ----------------------------------------------------------------- candidates

interface CandidatesTabProps extends TabProps {
  readonly onDecide: (candidateId: string, decision: "APPROVE" | "REJECT") => void;
}

function CandidatesTab({ workspaceId, tick, onDecide }: CandidatesTabProps) {
  const { client } = useAppState();
  const [candidates, setCandidates] = useState<readonly MemoryPromotionCandidateSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setCandidates(null);
    setError(null);
    client
      .listMemoryPromotionCandidates(workspaceId)
      .then((list) => {
        if (!cancelled) setCandidates(list);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      });
    return () => {
      cancelled = true;
    };
  }, [client, workspaceId, tick]);

  if (error) return <EmptyState title="Ошибка кандидатов">Ошибка: {error}</EmptyState>;
  if (!candidates) return <EmptyState title="Загрузка кандидатов…" />;

  const order = { PENDING: 0, APPROVED: 1, REJECTED: 2 } as const;
  const sorted = [...candidates].sort(
    (a, b) => order[a.decisionStatus] - order[b.decisionStatus]
  );

  const columns: readonly DataTableColumn<MemoryPromotionCandidateSummary>[] = [
    {
      key: "status",
      header: "статус",
      render: (c) => (
        <span
          className={`clab-badge ${
            c.decisionStatus === "PENDING"
              ? "clab-badge--warn"
              : c.decisionStatus === "APPROVED"
                ? "clab-badge--ok"
                : "clab-badge--danger"
          }`}
        >
          {STATUS_LABELS[c.decisionStatus] ?? c.decisionStatus}
        </span>
      ),
    },
    { key: "meaning", header: "текст", render: (c) => c.meaning, wrap: true },
    { key: "kind", header: "вид", render: (c) => c.memoryKind },
    {
      key: "epistemic",
      header: "эпистемика",
      render: (c) => (
        <span title={USER_REPORT_NOTE}>
          {c.epistemicKind} — {USER_REPORT_NOTE}
        </span>
      ),
      wrap: true,
    },
    { key: "source", header: "источник", render: (c) => shortId(c.sourceEventId) },
    {
      key: "action",
      header: "",
      render: (c) =>
        c.decisionStatus === "PENDING" ? (
          <Inline gap={1}>
            <button className="clab-btn clab-btn--primary" onClick={() => onDecide(c.candidateId, "APPROVE")}>
              Одобрить
            </button>
            <button className="clab-btn" onClick={() => onDecide(c.candidateId, "REJECT")}>
              Отклонить
            </button>
          </Inline>
        ) : null,
    },
  ];

  return (
    <Section title={`Кандидаты — ${candidates.length}`}>
      <DataTableShell columns={columns} rows={sorted} rowKey={(c) => c.candidateId} emptyMessage="Кандидатов нет." />
    </Section>
  );
}

// --------------------------------------------------------------- consolidated

interface ConsolidatedTabProps extends TabProps {
  readonly onRelate: (record: ConsolidatedMemoryRecordSummary) => void;
}

function ConsolidatedTab({ workspaceId, tick, onRelate }: ConsolidatedTabProps) {
  const { client } = useAppState();
  const [records, setRecords] = useState<readonly ConsolidatedMemoryRecordSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setRecords(null);
    setError(null);
    client
      .listConsolidatedMemory(workspaceId)
      .then((list) => {
        if (!cancelled) setRecords(list);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      });
    return () => {
      cancelled = true;
    };
  }, [client, workspaceId, tick]);

  if (error) return <EmptyState title="Ошибка долговременной памяти">Ошибка: {error}</EmptyState>;
  if (!records) return <EmptyState title="Загрузка долговременной памяти…" />;

  const columns: readonly DataTableColumn<ConsolidatedMemoryRecordSummary>[] = [
    {
      key: "status",
      header: "статус",
      render: (r) => (
        <Inline gap={1}>
          <span className={`clab-badge ${r.status === "ACTIVE" ? "clab-badge--ok" : "clab-badge--warn"}`}>
            {r.status}
          </span>
          {r.conflictRecordIds.length > 0 && (
            <span className="clab-badge clab-badge--danger">CONFLICT</span>
          )}
        </Inline>
      ),
    },
    { key: "meaning", header: "текст", render: (r) => r.meaning, wrap: true },
    { key: "kind", header: "вид", render: (r) => r.memoryKind },
    {
      key: "epistemic",
      header: "эпистемика",
      render: (r) => (
        <span title={USER_REPORT_NOTE}>
          {r.epistemicKind} — {USER_REPORT_NOTE}
        </span>
      ),
      wrap: true,
    },
    { key: "source", header: "источник", render: (r) => shortId(r.sourceEventId) },
    {
      key: "superseded",
      header: "вытеснена",
      render: (r) => (r.supersededByRecordId ? shortId(r.supersededByRecordId) : "—"),
    },
    {
      key: "action",
      header: "",
      render: (r) =>
        r.status === "ACTIVE" ? (
          <button className="clab-btn" onClick={() => onRelate(r)}>
            Связать память
          </button>
        ) : null,
    },
  ];

  return (
    <Section title={`Долговременная память — ${records.length}`}>
      <DataTableShell columns={columns} rows={records} rowKey={(r) => r.recordId} emptyMessage="Долговременная память пуста." />
    </Section>
  );
}

// ------------------------------------------------------------------- relation

interface RelationPanelProps {
  readonly workspaceId: string;
  readonly from: ConsolidatedMemoryRecordSummary;
  readonly tick: number;
  readonly onCancel: () => void;
  readonly onCreate: (targetId: string, kind: ConsolidatedRelationKind) => void;
}

function RelationPanel({ workspaceId, from, tick, onCancel, onCreate }: RelationPanelProps) {
  const { client } = useAppState();
  const [targets, setTargets] = useState<readonly ConsolidatedMemoryRecordSummary[]>([]);
  const [kind, setKind] = useState<ConsolidatedRelationKind>("SUPERSEDES");
  const [targetId, setTargetId] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    client
      .listConsolidatedMemory(workspaceId)
      .then((list) => {
        if (cancelled) return;
        // Never offer self as a target; same-workspace records only (backend
        // remains authoritative for all relation rules).
        const options = list.filter((r) => r.recordId !== from.recordId);
        setTargets(options);
        setTargetId(options[0]?.recordId ?? "");
      })
      .catch(() => {
        if (!cancelled) setTargets([]);
      });
    return () => {
      cancelled = true;
    };
  }, [client, workspaceId, from.recordId, tick]);

  return (
    <Section title="Связать память">
      <div className="clab-form-field__label">
        ОТ (текущая/новая запись): {from.meaning}
      </div>
      <Inline gap={2}>
        <select
          className="clab-select"
          value={kind}
          onChange={(e) => setKind(e.target.value as ConsolidatedRelationKind)}
        >
          {ALL_CONSOLIDATED_RELATION_KINDS.map((k) => (
            <option key={k} value={k}>
              {k}
            </option>
          ))}
        </select>
        <select
          className="clab-select"
          value={targetId}
          onChange={(e) => setTargetId(e.target.value)}
        >
          {targets.map((r) => (
            <option key={r.recordId} value={r.recordId}>
              {shortId(r.recordId)} — {r.meaning.slice(0, 60)}
            </option>
          ))}
        </select>
        <button
          className="clab-btn clab-btn--primary"
          disabled={!targetId}
          onClick={() => onCreate(targetId, kind)}
        >
          Создать связь
        </button>
        <button className="clab-btn" onClick={onCancel}>
          Отмена
        </button>
      </Inline>
    </Section>
  );
}
