"use client";

// Lịch khám của bác sĩ (D-day, D-week, D-day-m; UC12, FR-DOC-01, AC-09): chỉ lịch của chính mình,
// xem theo ngày hoặc tuần. Ngày và chế độ xem nằm trên URL (?date=&view=week); tự tải lại mỗi 60
// giây (docs mục 9.4). Điện thoại luôn xem theo ngày (docs mục 9.6). Bác sĩ không thấy email, số
// điện thoại của bệnh nhân: API không trả các trường này.
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState, type ReactNode } from "react";

import { errorMessage, toApiError } from "@/shared/api/errors";
import type { DoctorSchedule, ScheduleAppointment, TimeOffBlock } from "@/shared/api/types";
import { cn } from "@/shared/lib/cn";
import {
  addDays,
  clinicDay,
  formatDayFull,
  formatDayLong,
  formatDayShort,
  formatTime,
  formatTimeRange,
  formatWeekRange,
  isValidDay,
  mondayOf,
  todayInClinic,
} from "@/shared/lib/datetime";
import { TEXT } from "@/shared/texts";
import { Alert } from "@/shared/ui/alert";
import { StatusBadge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { CalendarIcon, ChevronLeftIcon, ChevronRightIcon, RefreshIcon } from "@/shared/ui/icons";
import { toast } from "@/shared/ui/toast";

import { givenName, summarize, visitActions, weekGrid } from "./plan";
import { useDoctorSchedule, useSetVisitStatus, type VisitStatus } from "./queries";
import { useNow } from "./use-now";

const T = TEXT.doctorArea;
const STATUS = TEXT.appointments.statuses;
const ACTION_LABEL: Record<VisitStatus, string> = {
  ARRIVED: T.arrived,
  COMPLETED: T.completed,
  NO_SHOW: T.noShow,
};

export function DoctorSchedulePage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const [today] = useState(todayInClinic);
  const rawDate = searchParams.get("date");
  const date = rawDate && isValidDay(rawDate) ? rawDate : today;
  const week = searchParams.get("view") === "week";
  const first = week ? mondayOf(date) : date;
  const last = week ? addDays(first, 6) : date;
  const schedule = useDoctorSchedule(first, last);

  function go(next: { date?: string; week?: boolean }) {
    const query = new URLSearchParams();
    const day = next.date ?? date;
    if (day !== today) query.set("date", day);
    if (next.week ?? week) query.set("view", "week");
    const text = query.toString();
    router.replace(text ? `${pathname}?${text}` : pathname, { scroll: false });
  }

  const step = week ? 7 : 1;
  const navButton =
    "flex size-10 items-center justify-center rounded-control border border-line-strong bg-surface hover:border-primary";

  return (
    <main className="mx-auto flex w-full max-w-[1200px] flex-col gap-4 px-4 py-5 md:px-7 md:py-6">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
        <h1 className="text-2xl font-semibold md:text-[26px] md:leading-[34px]">{T.title}</h1>
        <div className="flex items-center gap-1">
          <button
            type="button"
            aria-label={week ? T.prevWeek : T.prevDay}
            onClick={() => go({ date: addDays(date, -step) })}
            className={navButton}
          >
            <ChevronLeftIcon size={18} />
          </button>
          <label className="relative flex h-10 items-center gap-2 rounded-control border border-line-strong bg-surface px-3 font-semibold">
            <CalendarIcon size={16} className="text-muted" />
            <span className="tabular-nums">
              {week ? formatWeekRange(first) : formatDayFull(date)}
            </span>
            <input
              type="date"
              aria-label={T.pickDate}
              value={date}
              onChange={(event) => event.target.value && go({ date: event.target.value })}
              className="absolute inset-0 cursor-pointer opacity-0"
            />
          </label>
          <button
            type="button"
            aria-label={week ? T.nextWeek : T.nextDay}
            onClick={() => go({ date: addDays(date, step) })}
            className={navButton}
          >
            <ChevronRightIcon size={18} />
          </button>
          {date !== today ? (
            <Button size="sm" variant="ghost" onClick={() => go({ date: today })}>
              {T.today}
            </Button>
          ) : null}
        </div>
        <div
          role="group"
          aria-label={T.viewLabel}
          className="hidden gap-1 rounded-[10px] bg-divider p-[3px] md:flex"
        >
          {[false, true].map((value) => (
            <button
              key={String(value)}
              type="button"
              aria-pressed={week === value}
              onClick={() => go({ week: value })}
              className={cn(
                "h-9 rounded-control px-3.5",
                week === value ? "bg-surface font-semibold shadow-sm" : "text-muted",
              )}
            >
              {value ? T.week : T.day}
            </button>
          ))}
        </div>
        <span className="flex items-center gap-1.5 text-sm text-muted md:ml-auto">
          <RefreshIcon size={14} className={schedule.isFetching ? "animate-spin" : undefined} />
          {schedule.dataUpdatedAt
            ? T.updatedAt(formatTime(new Date(schedule.dataUpdatedAt)))
            : null}
        </span>
      </div>

      {schedule.isPending ? (
        <span aria-hidden="true" className="h-80 animate-pulse rounded-card bg-divider" />
      ) : schedule.isError ? (
        <div className="flex flex-col items-start gap-3">
          <Alert tone="danger">{T.loadError}</Alert>
          <Button size="sm" variant="secondary" onClick={() => void schedule.refetch()}>
            {TEXT.common.retry}
          </Button>
        </div>
      ) : week ? (
        <>
          <WeekView schedule={schedule.data} monday={first} today={today} />
          <div className="md:hidden">
            <DayView schedule={schedule.data} day={date} today={today} />
          </div>
        </>
      ) : (
        <DayView schedule={schedule.data} day={date} today={today} />
      )}
    </main>
  );
}

function Summary({ items }: { items: ScheduleAppointment[] }) {
  const s = summarize(items);
  const chips: [number, string][] = [
    [s.total, T.summary.total],
    [s.completed, T.summary.completed],
    [s.inProgress, T.summary.inProgress],
    [s.waiting, T.summary.waiting],
    [s.noShow, T.summary.noShow],
    [s.cancelled, T.summary.cancelled],
  ];
  return (
    <div className="flex flex-wrap gap-2">
      {chips.map(([count, label], index) =>
        index === 0 || count > 0 ? (
          <span
            key={label}
            className="rounded-full border border-line bg-surface px-3 py-1 text-sm"
          >
            <b className="tabular-nums">{count}</b> {label}
          </span>
        ) : null,
      )}
    </div>
  );
}

function VisitBadge({ status }: { status: ScheduleAppointment["status"] }) {
  // Với bác sĩ, bệnh nhân đã đến tức là đang khám (D-day).
  return status === "ARRIVED" ? (
    <span className="inline-flex items-center rounded-full bg-arrived-soft px-2.5 text-xs leading-6 font-semibold text-arrived">
      {T.inProgress}
    </span>
  ) : (
    <StatusBadge status={status} />
  );
}

function DayView({
  schedule,
  day,
  today,
}: {
  schedule: DoctorSchedule;
  day: string;
  today: string;
}) {
  const now = useNow();
  const items = schedule.appointments.filter((a) => clinicDay(a.start_at) === day);
  const shown = items.filter((a) => a.status !== "CANCELLED");
  const cancelled = items.length - shown.length;
  const work = schedule.work.filter((w) => clinicDay(w.start_at) === day);
  const nowIndex =
    day === today ? shown.findIndex((a) => Date.parse(a.start_at) > now.getTime()) : -2;

  const nowLine = (
    <li aria-label={T.now(formatTime(now))} className="flex items-center gap-2 py-1">
      <span className="w-12 shrink-0 text-xs font-bold text-danger tabular-nums">
        {formatTime(now)}
      </span>
      <span className="h-0.5 flex-1 rounded bg-danger" />
    </li>
  );

  return (
    <div className="flex flex-col gap-4">
      <Summary items={items} />
      <div className="flex flex-col gap-5 lg:flex-row lg:items-start">
        <div className="flex min-w-0 flex-1 flex-col gap-2">
          {shown.length === 0 ? (
            <p className="rounded-card border border-line bg-surface p-8 text-center text-muted">
              {T.empty}
            </p>
          ) : (
            <ol aria-label={T.timeline} className="flex flex-col gap-2">
              {shown.map((appointment, index) => (
                <VisitRow
                  key={appointment.id}
                  appointment={appointment}
                  now={now}
                  before={index === nowIndex ? nowLine : null}
                />
              ))}
              {nowIndex === -1 ? nowLine : null}
            </ol>
          )}
          {cancelled > 0 ? (
            <p className="text-sm text-muted">{T.cancelledCount(cancelled)}</p>
          ) : null}
        </div>
        <aside className="flex w-full shrink-0 flex-col gap-3 lg:w-[300px]">
          <section className="flex flex-col gap-1.5 rounded-card border border-line bg-surface p-4">
            <h2 className="font-semibold">{T.shiftsToday}</h2>
            {work.length === 0 ? (
              <span className="text-sm text-muted">{T.noShiftToday}</span>
            ) : (
              work.map((block) => (
                <span key={block.start_at} className="text-lg font-semibold tabular-nums">
                  {formatTimeRange(block.start_at, block.end_at)}
                </span>
              ))
            )}
          </section>
          <section className="flex flex-col gap-2 rounded-card border border-line bg-surface p-4">
            <h2 className="font-semibold">{T.upcomingTimeOffs}</h2>
            {schedule.upcoming_time_offs.length === 0 ? (
              <span className="text-sm text-muted">{T.noTimeOffs}</span>
            ) : (
              schedule.upcoming_time_offs.map((off) => <TimeOffLine key={off.start_at} off={off} />)
            )}
          </section>
        </aside>
      </div>
    </div>
  );
}

function TimeOffLine({ off }: { off: TimeOffBlock }) {
  const sameDay = clinicDay(off.start_at) === clinicDay(off.end_at);
  const allDay =
    sameDay && formatTime(off.start_at) === "00:00" && formatTime(off.end_at) >= "23:59";
  const when = sameDay
    ? `${formatDayLong(clinicDay(off.start_at))} · ${allDay ? T.allDay : formatTimeRange(off.start_at, off.end_at)}`
    : `${formatDayShort(clinicDay(off.start_at))} – ${formatDayShort(clinicDay(off.end_at))}`;
  return (
    <span className="flex flex-col text-sm">
      <b>{when}</b>
      <span className="text-muted">{[off.reason, T.timeOffBy].filter(Boolean).join(" · ")}</span>
    </span>
  );
}

function VisitRow({
  appointment,
  now,
  before,
}: {
  appointment: ScheduleAppointment;
  now: Date;
  before: ReactNode;
}) {
  const status = useSetVisitStatus();
  const actions = visitActions(appointment, now);
  const details = [
    appointment.reason ? `${T.reasonPrefix}${appointment.reason}` : null,
    appointment.has_note ? T.hasNote : null,
    appointment.channel === "AGENT" ? T.viaAgent : null,
  ].filter(Boolean);
  const href = `/doctor/appointments/${appointment.id}`;

  function set(target: VisitStatus) {
    status.mutate(
      { id: appointment.id, status: target },
      {
        onSuccess: () => toast.success(T.statusSaved(appointment.patient.name, STATUS[target])),
        onError: (error) => toast.error(errorMessage(toApiError(error))),
      },
    );
  }

  return (
    <>
      {before}
      <li className="flex gap-2">
        <span className="w-12 shrink-0 pt-3.5 text-sm font-semibold tabular-nums">
          {formatTime(appointment.start_at)}
        </span>
        <div
          className={cn(
            "flex min-w-0 flex-1 flex-wrap items-center gap-x-3 gap-y-2 rounded-card p-3",
            appointment.status === "ARRIVED"
              ? "border-[1.5px] border-arrived bg-surface"
              : appointment.status === "COMPLETED" || appointment.status === "NO_SHOW"
                ? "border border-line bg-ground"
                : "border border-line bg-surface",
          )}
        >
          <Link href={href} className="min-w-[200px] flex-1 hover:underline">
            <span className="block">
              <b>{appointment.patient.name}</b>
              {appointment.patient.age !== null
                ? `, ${T.years(appointment.patient.age)}`
                : null} · {appointment.service.name}
            </span>
            {details.length > 0 ? (
              <span className="block text-sm text-muted">{details.join(" · ")}</span>
            ) : null}
          </Link>
          <span className="flex flex-wrap items-center gap-2">
            <VisitBadge status={appointment.status} />
            {appointment.status === "ARRIVED" || appointment.status === "COMPLETED" ? (
              <Link
                href={href}
                className="rounded-control px-2 py-1 text-sm font-semibold text-primary hover:bg-primary-soft"
              >
                {T.note}
              </Link>
            ) : null}
            {actions.map((target) => (
              <Button
                key={target}
                size="sm"
                variant={target === "NO_SHOW" ? "secondary" : "primary"}
                disabled={status.isPending}
                onClick={() => set(target)}
              >
                {ACTION_LABEL[target]}
              </Button>
            ))}
          </span>
        </div>
      </li>
    </>
  );
}

const LEGEND_TONE: Record<string, string> = {
  BOOKED: "bg-booked-soft ring-1 ring-booked",
  ARRIVED: "bg-arrived-soft ring-1 ring-arrived",
  COMPLETED: "bg-completed-soft ring-1 ring-completed",
  NO_SHOW: "bg-noshow-soft ring-1 ring-noshow",
};

const CELL_TONE: Record<string, string> = {
  BOOKED: "bg-booked-soft text-booked",
  ARRIVED: "bg-arrived-soft text-arrived",
  COMPLETED: "bg-completed-soft text-completed",
  NO_SHOW: "bg-noshow-soft text-noshow",
};

function WeekView({
  schedule,
  monday,
  today,
}: {
  schedule: DoctorSchedule;
  monday: string;
  today: string;
}) {
  const grid = weekGrid(monday, schedule.appointments, schedule.work, schedule.time_offs);
  const total = schedule.appointments.filter((a) => a.status !== "CANCELLED").length;
  return (
    <div className="hidden flex-col gap-3 md:flex">
      <div className="flex flex-wrap items-center gap-3 text-sm">
        {Object.entries(T.legend).map(([status, label]) => (
          <span key={status} className="flex items-center gap-1.5">
            <span aria-hidden="true" className={cn("size-3 rounded-sm", LEGEND_TONE[status])} />
            {label}
          </span>
        ))}
        <span className="flex items-center gap-1.5">
          <span
            aria-hidden="true"
            className="size-3 rounded-sm bg-ground ring-1 ring-line-strong"
          />
          {T.outsideShift}
        </span>
      </div>
      {total === 0 ? <p className="text-sm text-muted">{T.emptyWeek}</p> : null}
      <div className="overflow-x-auto rounded-card border border-line bg-surface">
        <div className="grid min-w-[820px] grid-cols-[56px_repeat(7,minmax(0,1fr))] text-xs">
          <span className="border-b border-line" />
          {grid.days.map((day) => (
            <span
              key={day}
              className={cn(
                "flex flex-col items-center border-b border-l border-line py-2",
                day === today && "bg-primary-soft",
              )}
            >
              <span className="text-muted">
                {formatDayShort(day).split(" ")[0]}
                {day === today ? ` · ${T.today.toLowerCase()}` : null}
              </span>
              <b className="text-sm tabular-nums">{formatDayShort(day).split(" ")[1]}</b>
            </span>
          ))}
          {grid.rows.map((slot, row) => (
            <div key={slot} className="contents">
              <span className="border-b border-divider px-1.5 py-1 text-right text-muted tabular-nums">
                {slot.endsWith(":00") ? slot : ""}
              </span>
              {grid.cells[row]!.map((cell, column) => (
                <div
                  key={grid.days[column]}
                  className={cn(
                    "flex min-h-[30px] flex-col gap-0.5 border-b border-l border-divider p-0.5",
                    cell.off ? "bg-amber-soft" : !cell.working && "bg-ground",
                  )}
                >
                  {/* Nhãn ngày nghỉ chỉ ở ô đầu của khoảng nghỉ trong cột */}
                  {cell.off &&
                  cell.appointments.length === 0 &&
                  grid.cells[row - 1]?.[column]?.off !== cell.off ? (
                    <span className="px-1 text-[11px] leading-4 text-amber-ink">
                      {T.offLabel(cell.off.reason)}
                    </span>
                  ) : null}
                  {cell.appointments.map((a) => (
                    <Link
                      key={a.id}
                      href={`/doctor/appointments/${a.id}`}
                      className={cn(
                        "truncate rounded-[4px] px-1 leading-5 font-semibold hover:underline",
                        CELL_TONE[a.status],
                      )}
                    >
                      {formatTime(a.start_at)} {givenName(a.patient.name)}
                    </Link>
                  ))}
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
      <p className="text-sm text-muted">{T.weekNote}</p>
    </div>
  );
}
