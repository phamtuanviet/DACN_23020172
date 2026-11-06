"use client";

// Chi tiết lịch hẹn cho bác sĩ (D-detail; UC18, FR-DOC-02, FR-DOC-03, AC-17): bệnh nhân (họ tên,
// tuổi), giờ, dịch vụ, lý do khám; đổi trạng thái trong ngày; ghi chú sau khám tối đa 1.000 ký tự
// mà bệnh nhân xem được; lịch sử thay đổi và các lần khám trước với chính bác sĩ này.
import Link from "next/link";
import { useState } from "react";

import { errorMessage, toApiError } from "@/shared/api/errors";
import type { AppointmentDetail } from "@/shared/api/types";
import { describeHistory, historyChannel } from "@/shared/appointments/describe";
import { useAppointment } from "@/shared/appointments/queries";
import { cn } from "@/shared/lib/cn";
import {
  clinicDay,
  formatDayFull,
  formatDayLong,
  formatStamp,
  formatTime,
  formatTimeRange,
} from "@/shared/lib/datetime";
import { TEXT } from "@/shared/texts";
import { Alert } from "@/shared/ui/alert";
import { Avatar } from "@/shared/ui/avatar";
import { StatusBadge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";
import { inputClass } from "@/shared/ui/field";
import { CheckIcon } from "@/shared/ui/icons";
import { toast } from "@/shared/ui/toast";

import { visitActions } from "./plan";
import { useSaveNote, useSetVisitStatus, type VisitStatus } from "./queries";
import { useNow } from "./use-now";

const T = TEXT.doctorArea;
const STATUS = TEXT.appointments.statuses;
const NOTE_MAX = 1000;
const ACTION_LABEL: Record<VisitStatus, string> = {
  ARRIVED: T.markArrived,
  COMPLETED: T.markCompleted,
  NO_SHOW: T.markNoShow,
};

export function DoctorAppointmentPage({ id }: { id: number }) {
  const query = useAppointment(id);

  if (query.isPending)
    return (
      <main className="mx-auto w-full max-w-[1200px] px-4 py-6 md:px-7">
        <span aria-hidden="true" className="block h-96 animate-pulse rounded-card bg-divider" />
      </main>
    );
  if (query.isError)
    return (
      <main className="mx-auto flex w-full max-w-[1200px] flex-col items-start gap-3 px-4 py-6 md:px-7">
        <Alert tone="danger">
          {toApiError(query.error).code === "NOT_FOUND"
            ? T.notFound
            : errorMessage(toApiError(query.error))}
        </Alert>
        <Link href="/doctor/schedule" className="font-semibold text-primary">
          {TEXT.staff.schedule}
        </Link>
      </main>
    );
  return <Detail detail={query.data} />;
}

function Detail({ detail }: { detail: AppointmentDetail }) {
  const day = clinicDay(detail.start_at);
  const minutes = Math.round((Date.parse(detail.end_at) - Date.parse(detail.start_at)) / 60_000);
  const channel = TEXT.appointments.bookedVia[detail.channel].toLowerCase();

  return (
    <main className="mx-auto flex w-full max-w-[1200px] flex-col gap-4 px-4 py-5 md:px-7 md:py-6">
      <nav aria-label={T.breadcrumb} className="flex flex-wrap items-center gap-1.5 text-sm">
        <Link href={`/doctor/schedule?date=${day}`} className="font-semibold text-primary">
          {T.backToDay(formatDayLong(day))}
        </Link>
        <span aria-hidden="true" className="text-muted">
          /
        </span>
        <span className="text-muted">
          {formatTime(detail.start_at)} {detail.patient.name}
        </span>
      </nav>
      <div className="flex flex-col gap-5 lg:flex-row lg:items-start">
        <div className="flex min-w-0 flex-1 flex-col gap-4">
          <Card className="flex flex-col gap-4 p-5">
            <div className="flex items-center gap-3">
              <Avatar id={detail.patient.id} name={detail.patient.name} size="md" />
              <span className="flex flex-col">
                <span className="text-xl font-semibold">{detail.patient.name}</span>
                {detail.patient.age !== null ? (
                  <span className="text-muted">{T.years(detail.patient.age)}</span>
                ) : null}
              </span>
              <StatusBadge status={detail.status} className="ml-auto" />
            </div>
            <dl className="grid grid-cols-[120px_minmax(0,1fr)] gap-x-3 gap-y-2.5">
              <dt className="text-muted">{T.visitTime}</dt>
              <dd className="font-semibold tabular-nums">
                {formatTimeRange(detail.start_at, detail.end_at)} · {formatDayFull(day)}
              </dd>
              <dt className="text-muted">{T.service}</dt>
              <dd>
                {detail.service.name} · {TEXT.admin.minutes(minutes)}
              </dd>
              <dt className="text-muted">{T.reason}</dt>
              <dd className={detail.reason ? undefined : "text-muted"}>
                {detail.reason ?? T.noReason}
              </dd>
              <dt className="text-muted">{T.code}</dt>
              <dd className="tabular-nums">
                {detail.code} · {channel}
              </dd>
            </dl>
          </Card>
          <StatusCard detail={detail} />
          <NoteCard detail={detail} />
        </div>
        <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[340px]">
          <Card className="flex flex-col gap-3 p-5">
            <h2 className="font-semibold">{T.historyTitle}</h2>
            <ol className="flex flex-col gap-3">
              {[...detail.history].reverse().map((entry) => (
                <li key={`${entry.created_at}-${entry.action}`} className="flex gap-2.5">
                  <span
                    aria-hidden="true"
                    className="mt-1.5 size-2 shrink-0 rounded-full bg-primary"
                  />
                  <span className="flex flex-col">
                    <span>{describeHistory(entry)}</span>
                    <span className="text-sm text-muted tabular-nums">
                      {formatStamp(entry.created_at)} · {historyChannel(entry)}
                    </span>
                  </span>
                </li>
              ))}
            </ol>
          </Card>
          <Card className="flex flex-col gap-3 p-5">
            <h2 className="font-semibold">{T.previousTitle}</h2>
            {detail.previous_visits.length === 0 ? (
              <p className="text-sm text-muted">{T.previousEmpty}</p>
            ) : (
              detail.previous_visits.map((visit) => (
                <Link
                  key={visit.id}
                  href={`/doctor/appointments/${visit.id}`}
                  className="flex flex-col gap-1 rounded-[10px] border border-line p-3 hover:border-primary"
                >
                  <span className="flex items-center justify-between gap-2">
                    <b className="tabular-nums">{formatDayFull(clinicDay(visit.start_at))}</b>
                    <StatusBadge status={visit.status} />
                  </span>
                  <span className="text-sm">{visit.service.name}</span>
                  {visit.doctor_note ? (
                    <span className="line-clamp-3 text-sm text-muted">
                      {T.notePrefix}
                      {visit.doctor_note}
                    </span>
                  ) : null}
                </Link>
              ))
            )}
            <p className="text-xs text-muted">{T.previousNote}</p>
          </Card>
        </aside>
      </div>
    </main>
  );
}

function StatusCard({ detail }: { detail: AppointmentDetail }) {
  const now = useNow();
  const change = useSetVisitStatus();
  const actions = visitActions(detail, now);
  const arrivedAt = detail.history.findLast(
    (entry) => entry.action === "STATUS_CHANGE" && entry.new?.status === "ARRIVED",
  )?.created_at;
  const final = ["COMPLETED", "NO_SHOW", "CANCELLED"].includes(detail.status);
  const today = clinicDay(detail.start_at) === clinicDay(now);

  const steps: { label: string; done: boolean; current: boolean }[] =
    detail.status === "NO_SHOW" || detail.status === "CANCELLED"
      ? [
          { label: STATUS.BOOKED, done: true, current: false },
          { label: STATUS[detail.status], done: true, current: true },
        ]
      : [
          { label: STATUS.BOOKED, done: true, current: detail.status === "BOOKED" },
          {
            label: arrivedAt ? `${STATUS.ARRIVED} · ${formatTime(arrivedAt)}` : STATUS.ARRIVED,
            done: detail.status !== "BOOKED",
            current: detail.status === "ARRIVED",
          },
          {
            label: STATUS.COMPLETED,
            done: detail.status === "COMPLETED",
            current: detail.status === "COMPLETED",
          },
        ];

  const hint = final
    ? T.finalHint
    : !today
      ? T.notTodayHint
      : detail.status === "ARRIVED"
        ? T.arrivedHint
        : actions.includes("NO_SHOW")
          ? null
          : T.noShowHint;

  function set(target: VisitStatus) {
    change.mutate(
      { id: detail.id, status: target },
      {
        onSuccess: () => toast.success(T.statusSaved(detail.patient.name, STATUS[target])),
        onError: (error) => toast.error(errorMessage(toApiError(error))),
      },
    );
  }

  return (
    <Card className="flex flex-col gap-4 p-5">
      <h2 className="font-semibold">{T.statusTitle}</h2>
      <ol aria-label={T.progressLabel} className="flex flex-wrap items-center gap-2">
        {steps.map((step, index) => (
          <li key={step.label} className="flex items-center gap-2">
            {index > 0 ? (
              <span
                aria-hidden="true"
                className={cn("h-0.5 w-8", step.done ? "bg-primary" : "bg-line")}
              />
            ) : null}
            <span
              aria-current={step.current ? "step" : undefined}
              className={cn(
                "flex items-center gap-1.5 rounded-full px-3 py-1 text-sm",
                step.current
                  ? "bg-primary font-semibold text-white"
                  : step.done
                    ? "bg-primary-soft text-primary-ink"
                    : "border border-line text-muted",
              )}
            >
              {step.done && !step.current ? <CheckIcon size={14} /> : null}
              {step.label}
            </span>
          </li>
        ))}
      </ol>
      {actions.length > 0 ? (
        <div className="flex flex-wrap items-center gap-2">
          {[...actions].reverse().map((target) => (
            <Button
              key={target}
              variant={target === "NO_SHOW" ? "secondary" : "primary"}
              loading={change.isPending && change.variables?.status === target}
              disabled={change.isPending}
              onClick={() => set(target)}
            >
              {ACTION_LABEL[target]}
            </Button>
          ))}
        </div>
      ) : null}
      {hint ? <p className="text-sm text-muted">{hint}</p> : null}
    </Card>
  );
}

function NoteCard({ detail }: { detail: AppointmentDetail }) {
  const saved = detail.doctor_note ?? "";
  const [note, setNote] = useState(saved);
  const save = useSaveNote();
  const open = detail.status === "ARRIVED" || detail.status === "COMPLETED";
  const dirty = note.trim() !== saved;
  const error = save.error ? toApiError(save.error) : null;

  function submit() {
    save.mutate(
      { id: detail.id, note },
      {
        onSuccess: (updated) => {
          setNote(updated.doctor_note ?? "");
          toast.success(T.noteSaved);
        },
      },
    );
  }

  return (
    <Card className="flex flex-col gap-3 p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-semibold">{T.noteTitle}</h2>
        <span className="text-sm text-muted">{T.notePatientSees}</span>
      </div>
      <label htmlFor="doctor-note" className="sr-only">
        {T.noteLabel}
      </label>
      <textarea
        id="doctor-note"
        rows={5}
        value={note}
        maxLength={NOTE_MAX}
        disabled={!open}
        placeholder={open ? T.notePlaceholder : T.noteLocked}
        onChange={(event) => {
          setNote(event.target.value);
          save.reset();
        }}
        className={inputClass(Boolean(error), "multiline")}
      />
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm text-muted tabular-nums" aria-live="polite">
          {T.noteCounter(note.length, NOTE_MAX)}
          {dirty ? ` · ${T.noteUnsaved}` : null}
        </span>
        <Button
          onClick={submit}
          disabled={!open || !dirty}
          loading={save.isPending}
          loadingText={TEXT.admin.saving}
        >
          {T.noteSave}
        </Button>
      </div>
      {error ? <Alert tone="danger">{errorMessage(error)}</Alert> : null}
    </Card>
  );
}
