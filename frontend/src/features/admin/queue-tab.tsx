// Chỉ dùng trong client component.
// Hàng chờ cần xử lý (AD-queue, FR-ADM-04): lịch bị gắn cờ vì bác sĩ nghỉ hoặc đổi ca (BR-10) và
// yêu cầu gặp nhân viên do trợ lý chuyển sang (UC11). Quản trị đổi, hủy hoặc gỡ cờ từng lịch; gọi
// lại bệnh nhân rồi đánh dấu yêu cầu đã xử lý.
import { useState } from "react";

import { errorMessage, toApiError } from "@/shared/api/errors";
import type { AdminAppointment, SupportRequest } from "@/shared/api/types";
import { cn } from "@/shared/lib/cn";
import { clinicDay, formatDayShort, formatStamp, formatTime } from "@/shared/lib/datetime";
import { formatPhone } from "@/shared/lib/format";
import { TEXT } from "@/shared/texts";
import { Alert } from "@/shared/ui/alert";
import { Button, buttonClass } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";
import { FlagIcon, HeadsetIcon, PhoneIcon } from "@/shared/ui/icons";
import { toast } from "@/shared/ui/toast";

import { AdminDialogs, type AdminDialog } from "./appointment-actions";
import {
  useAdminAppointments,
  useSetAttention,
  useSupportRequests,
  useUpdateSupportRequest,
} from "./queries";

const T = TEXT.admin;
const FLAGGED_PAGE = 100;

export function QueueTab() {
  const [dialog, setDialog] = useState<AdminDialog>(null);
  const flagged = useAdminAppointments({ needsAttention: true, page: 1, pageSize: FLAGGED_PAGE });
  const [supportStatus, setSupportStatus] = useState<"OPEN" | "DONE">("OPEN");
  const support = useSupportRequests(supportStatus);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const requests = support.data ?? [];
  const selected = requests.find((r) => r.id === selectedId) ?? requests[0];

  return (
    <div className="flex flex-col gap-5 lg:flex-row lg:items-start">
      <div className="flex min-w-0 flex-1 flex-col gap-5">
        <FlaggedSection
          items={flagged.data?.items ?? []}
          total={flagged.data?.total}
          loading={flagged.isPending}
          failed={flagged.isError}
          onOpen={setDialog}
        />
        <Card className="flex flex-col gap-3 p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-lg font-semibold">
              {T.supportTitle}
              {supportStatus === "OPEN" && support.data ? (
                <span className="font-normal text-muted"> · {requests.length}</span>
              ) : null}
            </h2>
            <div
              role="group"
              aria-label={T.supportStatus}
              className="flex gap-1 rounded-[10px] bg-divider p-[3px]"
            >
              {(["OPEN", "DONE"] as const).map((value) => (
                <button
                  key={value}
                  type="button"
                  aria-pressed={supportStatus === value}
                  onClick={() => {
                    setSupportStatus(value);
                    setSelectedId(null);
                  }}
                  className={cn(
                    "h-8 rounded-control px-3 text-sm",
                    supportStatus === value ? "bg-surface font-semibold" : "text-muted",
                  )}
                >
                  {value === "OPEN" ? T.supportOpen : T.supportDone}
                </button>
              ))}
            </div>
          </div>
          {support.isPending ? (
            <span aria-hidden="true" className="h-16 animate-pulse rounded-[10px] bg-divider" />
          ) : support.isError ? (
            <Alert tone="danger">{T.loadError}</Alert>
          ) : requests.length === 0 ? (
            <p className="text-muted">
              {supportStatus === "OPEN" ? T.supportEmpty : T.supportDoneEmpty}
            </p>
          ) : (
            <ul className="flex flex-col gap-2">
              {requests.map((request) => (
                <li key={request.id}>
                  <button
                    type="button"
                    aria-pressed={request.id === selected?.id}
                    onClick={() => setSelectedId(request.id)}
                    className={cn(
                      "flex w-full items-start gap-3 rounded-[10px] p-3 text-left",
                      request.id === selected?.id
                        ? "border-[1.5px] border-primary bg-primary-soft"
                        : "border border-line hover:border-primary",
                    )}
                  >
                    <HeadsetIcon size={20} className="mt-0.5 shrink-0 text-primary" />
                    <span className="min-w-0 flex-1">
                      <span className="block">
                        <b>{request.patient.name}</b> · {formatStamp(request.created_at)}
                      </span>
                      <span className="line-clamp-2 text-sm text-muted">{request.summary}</span>
                    </span>
                    <SupportBadge status={request.status} />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
      {selected ? <SupportDetail request={selected} /> : null}
      <AdminDialogs dialog={dialog} onClose={() => setDialog(null)} />
    </div>
  );
}

function FlaggedSection({
  items,
  total,
  loading,
  failed,
  onOpen,
}: {
  items: AdminAppointment[];
  total: number | undefined;
  loading: boolean;
  failed: boolean;
  onOpen: (dialog: NonNullable<AdminDialog>) => void;
}) {
  const attention = useSetAttention();
  return (
    <section className="flex flex-col gap-3 rounded-card border border-amber-line bg-[#fffbf1] p-5">
      <h2 className="flex items-center gap-2 text-lg font-semibold">
        <FlagIcon size={18} className="text-amber" />
        {T.flaggedTitle}
        {total !== undefined ? <span className="font-normal text-muted">· {total}</span> : null}
      </h2>
      <p className="text-sm text-muted">{T.flaggedLead}</p>
      {loading ? (
        <span aria-hidden="true" className="h-16 animate-pulse rounded-[10px] bg-divider" />
      ) : failed ? (
        <Alert tone="danger">{T.loadError}</Alert>
      ) : items.length === 0 ? (
        <p className="font-semibold text-success">{T.flaggedEmpty}</p>
      ) : (
        <ul className="flex flex-col divide-y divide-amber-line">
          {items.map((item) => (
            <li key={item.id} className="flex flex-wrap items-center gap-3 py-3">
              <span className="min-w-0 flex-1">
                <span className="block font-semibold tabular-nums">
                  {formatTime(item.start_at)} · {formatDayShort(clinicDay(item.start_at))} ·{" "}
                  {item.patient.name}
                </span>
                <span className="block text-sm text-muted">
                  {item.service.name} · {item.doctor.name} · {item.code}
                </span>
                <span className="block text-sm text-muted">
                  {[
                    item.attention_source ? T.attentionSources[item.attention_source] : null,
                    item.patient.phone ? formatPhone(item.patient.phone) : null,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </span>
              </span>
              <span className="flex flex-wrap gap-2">
                {item.status === "BOOKED" ? (
                  <>
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => onOpen({ kind: "reschedule", appointment: item })}
                    >
                      {T.reschedule}
                    </Button>
                    <Button
                      size="sm"
                      variant="danger"
                      onClick={() => onOpen({ kind: "cancel", appointment: item })}
                    >
                      {T.cancel}
                    </Button>
                  </>
                ) : null}
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={attention.isPending}
                  onClick={() =>
                    attention.mutate(
                      { id: item.id, value: false },
                      {
                        onSuccess: () => toast.success(T.unflagged(item.code)),
                        onError: (error) => toast.error(errorMessage(toApiError(error))),
                      },
                    )
                  }
                >
                  {T.unflag}
                </Button>
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function SupportBadge({ status }: { status: SupportRequest["status"] }) {
  return (
    <span
      className={cn(
        "shrink-0 rounded-full px-2.5 text-xs leading-6 font-semibold",
        status === "OPEN" ? "bg-amber-soft text-amber-ink" : "bg-completed-soft text-completed",
      )}
    >
      {status === "OPEN" ? T.supportOpen : T.supportDone}
    </span>
  );
}

function SupportDetail({ request }: { request: SupportRequest }) {
  const update = useUpdateSupportRequest();
  const done = request.status === "DONE";

  function toggle() {
    update.mutate(
      { id: request.id, status: done ? "OPEN" : "DONE" },
      {
        onSuccess: () => toast.success(done ? T.reopened : T.markedDone),
        onError: (error) => toast.error(errorMessage(toApiError(error))),
      },
    );
  }

  return (
    <aside
      aria-label={T.supportDetail(request.id)}
      className="flex w-full shrink-0 flex-col gap-4 rounded-card border border-line bg-surface p-5 shadow-sm lg:sticky lg:top-6 lg:w-[360px]"
    >
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">{T.supportDetail(request.id)}</h2>
        <SupportBadge status={request.status} />
      </div>
      <dl className="grid grid-cols-[96px_minmax(0,1fr)] gap-x-3 gap-y-2 text-sm">
        <dt className="text-muted">{T.patient}</dt>
        <dd className="font-semibold">{request.patient.name}</dd>
        <dt className="text-muted">{T.phone}</dt>
        <dd>
          {request.patient.phone ? (
            <a href={`tel:${request.patient.phone}`} className="font-semibold text-primary">
              {formatPhone(request.patient.phone)}
            </a>
          ) : (
            T.noPhone
          )}
        </dd>
        <dt className="text-muted">{T.email}</dt>
        <dd className="break-all">{request.patient.email}</dd>
        <dt className="text-muted">{T.receivedAt}</dt>
        <dd className="tabular-nums">{formatStamp(request.created_at)}</dd>
      </dl>
      <div className="flex flex-col gap-1.5 rounded-[10px] bg-ground p-3">
        <span className="text-sm font-semibold text-muted">{T.summary}</span>
        <p className="whitespace-pre-line">{request.summary}</p>
      </div>
      {done && request.handled_by && request.handled_at ? (
        <p className="text-sm text-muted">
          {T.handledBy(request.handled_by, formatStamp(request.handled_at))}
        </p>
      ) : null}
      <div className="flex flex-wrap gap-2">
        {request.patient.phone ? (
          <a
            href={`tel:${request.patient.phone}`}
            className={buttonClass({ variant: "secondary", size: "sm" })}
          >
            <PhoneIcon size={16} />
            {T.callPatient}
          </a>
        ) : null}
        <Button
          size="sm"
          variant={done ? "secondary" : "primary"}
          loading={update.isPending}
          loadingText={T.saving}
          onClick={toggle}
        >
          {done ? T.reopen : T.markDone}
        </Button>
      </div>
    </aside>
  );
}
