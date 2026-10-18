// Chỉ dùng trong client component. Chi tiết lịch hẹn (P-appts, cột phải): giờ, dịch vụ, bác sĩ,
// lý do, nút đổi/hủy kèm hạn 2 giờ (BR-08), ghi chú bác sĩ (FR-DOC-03), lịch sử thay đổi (FR-APT-05).
import Link from "next/link";
import { useState } from "react";

import type { Appointment, AppointmentDetail as Detail } from "@/shared/api/types";
import { describeHistory, historyChannel } from "@/shared/appointments/describe";
import { useAppointment } from "@/shared/appointments/queries";
import {
  clinicDay,
  formatDayFull,
  formatDayLong,
  formatStamp,
  formatTime,
  formatTimeRange,
} from "@/shared/lib/datetime";
import { CLINIC, TEXT } from "@/shared/texts";
import { Alert } from "@/shared/ui/alert";
import { StatusBadge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";

const T = TEXT.appointments;

export function AppointmentDetail({
  id,
  backHref,
  onReschedule,
  onCancel,
}: {
  id: number;
  backHref: string;
  onReschedule: (appointment: Appointment) => void;
  onCancel: (appointment: Appointment) => void;
}) {
  const query = useAppointment(id);

  return (
    <section
      aria-label={T.detailLabel}
      className="flex min-w-0 flex-col gap-4 rounded-card border border-line bg-surface p-5 lg:sticky lg:top-24"
    >
      <Link
        href={backHref}
        replace
        scroll={false}
        className="text-sm font-semibold text-primary lg:hidden"
      >
        {T.backToList}
      </Link>
      {query.isPending ? (
        <div aria-hidden="true" className="flex flex-col gap-3">
          <span className="h-7 w-40 animate-pulse rounded bg-divider" />
          <span className="h-20 animate-pulse rounded-[10px] bg-divider" />
          <span className="h-32 animate-pulse rounded-[10px] bg-divider" />
        </div>
      ) : query.isError ? (
        <div className="flex flex-col items-start gap-3">
          <Alert tone="danger">{T.loadError}</Alert>
          <Button variant="secondary" size="sm" onClick={() => void query.refetch()}>
            {TEXT.common.retry}
          </Button>
        </div>
      ) : (
        <DetailBody detail={query.data} onReschedule={onReschedule} onCancel={onCancel} />
      )}
    </section>
  );
}

function DetailBody({
  detail,
  onReschedule,
  onCancel,
}: {
  detail: Detail;
  onReschedule: (appointment: Appointment) => void;
  onCancel: (appointment: Appointment) => void;
}) {
  const [now] = useState(() => Date.now());
  const upcoming = detail.status === "BOOKED" && Date.parse(detail.start_at) > now;
  const rows: [string, string][] = [
    [TEXT.booking.summaryService, detail.service.name],
    [TEXT.booking.summaryDoctor, detail.doctor.name],
    ...(detail.reason ? [[T.reasonLabel, detail.reason] as [string, string]] : []),
    ...(detail.cancel_reason
      ? [[T.cancelReasonLabel, detail.cancel_reason] as [string, string]]
      : []),
  ];
  const history = [...detail.history].reverse(); // mới nhất ở trên

  return (
    <>
      <div className="flex items-center justify-between gap-3">
        <span className="font-mono text-lg font-bold tracking-wide">{detail.code}</span>
        <StatusBadge status={detail.status} />
      </div>
      <div className="flex flex-col rounded-[10px] bg-primary-soft px-4 py-3 text-primary-ink">
        <span className="font-semibold">{formatDayFull(clinicDay(detail.start_at))}</span>
        <span className="text-xl font-bold tabular-nums">
          {formatTimeRange(detail.start_at, detail.end_at)}
        </span>
      </div>
      <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-2 text-[15px]">
        {rows.map(([label, value]) => (
          <div key={label} className="contents">
            <dt className="text-muted">{label}</dt>
            <dd className="min-w-0 font-medium break-words">{value}</dd>
          </div>
        ))}
      </dl>

      {detail.needs_attention && detail.status === "BOOKED" ? (
        <Alert tone="warning">{T.attention}</Alert>
      ) : null}

      {detail.can_change ? (
        <div className="flex flex-col gap-2">
          <div className="grid grid-cols-2 gap-2">
            <Button variant="outline" onClick={() => onReschedule(detail)}>
              {T.reschedule}
            </Button>
            <Button variant="danger" onClick={() => onCancel(detail)}>
              {T.cancel}
            </Button>
          </div>
          {detail.change_until ? (
            <p className="text-sm text-muted">
              {T.changeUntil(
                `${formatTime(detail.change_until)} ${formatDayLong(clinicDay(detail.change_until))}`,
              )}
            </p>
          ) : null}
        </div>
      ) : upcoming ? (
        <Alert tone="warning">{T.locked(CLINIC.phone)}</Alert>
      ) : null}

      <div className="flex flex-col gap-1.5 border-t border-divider pt-4">
        <h2 className="font-semibold">{T.doctorNote}</h2>
        <p className={detail.doctor_note ? "whitespace-pre-line" : "text-sm text-muted"}>
          {detail.doctor_note || T.noDoctorNote}
        </p>
      </div>

      <div className="flex flex-col gap-2 border-t border-divider pt-4">
        <h2 className="font-semibold">{T.historyTitle}</h2>
        <ol className="flex flex-col gap-3">
          {history.map((entry, index) => (
            <li key={`${entry.created_at}-${index}`} className="flex gap-3">
              <span
                aria-hidden="true"
                className="mt-1.5 size-2.5 shrink-0 rounded-full border-2 border-primary"
              />
              <span className="flex min-w-0 flex-col">
                <span className="text-[15px] font-medium">{describeHistory(entry)}</span>
                <span className="text-sm text-muted">
                  {formatStamp(entry.created_at)} · {historyChannel(entry)}
                </span>
              </span>
            </li>
          ))}
        </ol>
      </div>
    </>
  );
}
