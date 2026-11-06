"use client";

// Lịch của tôi (P-appts, P-appts-m; UC08): tab Sắp tới, Lịch sử, lọc theo trạng thái (FR-APT-04).
// Tab, bộ lọc và lịch đang xem nằm trên URL (?tab=&status=&id=) nên Back và tải lại trang giữ
// nguyên chỗ. Máy tính: danh sách bên trái, chi tiết bên phải; điện thoại: bấm thẻ để xem chi tiết.
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import type { Appointment, AppointmentScope, AppointmentStatus } from "@/shared/api/types";
import { CancelDialog } from "@/shared/appointments/cancel-dialog";
import { useMyAppointmentList } from "@/shared/appointments/queries";
import { RescheduleDialog } from "@/shared/appointments/reschedule-dialog";
import { cn } from "@/shared/lib/cn";
import { dayBadge, formatTimeRange } from "@/shared/lib/datetime";
import { CLINIC, TEXT } from "@/shared/texts";
import { Alert } from "@/shared/ui/alert";
import { StatusBadge } from "@/shared/ui/badge";
import { Button, buttonClass } from "@/shared/ui/button";
import { inputClass } from "@/shared/ui/field";
import { CalendarPlusIcon, InfoIcon } from "@/shared/ui/icons";

import { AppointmentDetail } from "./appointment-detail";

const T = TEXT.appointments;
const ACTIVE_LIMIT = 3; // BR-09
const FILTERS: Record<AppointmentScope, AppointmentStatus[]> = {
  upcoming: ["BOOKED", "ARRIVED"],
  history: ["COMPLETED", "CANCELLED", "NO_SHOW"],
};

type DialogState = { kind: "reschedule" | "cancel"; appointment: Appointment } | null;

function parseId(value: string | null): number | undefined {
  return value && /^\d+$/.test(value) ? Number(value) : undefined;
}

export function MyAppointmentsPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const tab: AppointmentScope = searchParams.get("tab") === "history" ? "history" : "upcoming";
  const rawStatus = searchParams.get("status") as AppointmentStatus | null;
  const status = rawStatus && FILTERS[tab].includes(rawStatus) ? rawStatus : undefined;
  const explicitId = parseId(searchParams.get("id"));
  const [dialog, setDialog] = useState<DialogState>(null);
  const [now] = useState(() => Date.now());

  const upcoming = useMyAppointmentList("upcoming", tab === "upcoming" ? status : undefined);
  const history = useMyAppointmentList("history", tab === "history" ? status : undefined);
  const active = tab === "upcoming" ? upcoming : history;
  const items = active.data?.pages.flatMap((page) => page.items) ?? [];
  const selectedId = explicitId ?? items[0]?.id;
  const totalOf = (query: typeof upcoming) => query.data?.pages[0]?.total;

  function href(params: { tab?: AppointmentScope; status?: AppointmentStatus; id?: number }) {
    const query = new URLSearchParams();
    if (params.tab === "history") query.set("tab", "history");
    if (params.status) query.set("status", params.status);
    if (params.id !== undefined) query.set("id", String(params.id));
    const text = query.toString();
    return text ? `${pathname}?${text}` : pathname;
  }

  // Lịch đang chờ khám (BR-09): chỉ đếm được khi danh sách sắp tới không bị lọc.
  const activeCount =
    tab === "upcoming" && status
      ? undefined
      : (upcoming.data?.pages ?? [])
          .flatMap((page) => page.items)
          .filter((a) => a.status === "BOOKED" && Date.parse(a.start_at) > now).length;

  return (
    <main className="mx-auto flex w-full max-w-[1200px] flex-col gap-5 px-4 pt-6 pb-28 md:px-6 md:pb-12">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-2xl leading-8 font-semibold md:text-[28px] md:leading-9">{T.title}</h1>
        <Link href="/booking" className={buttonClass({ size: "sm" })}>
          <CalendarPlusIcon size={18} />
          {T.newBooking}
        </Link>
      </div>

      <div className="flex flex-wrap items-end justify-between gap-3">
        <div role="tablist" aria-label={T.tabsLabel} className="flex rounded-control bg-ground p-1">
          {(["upcoming", "history"] as const).map((scope) => {
            const selected = scope === tab;
            const total = totalOf(scope === "upcoming" ? upcoming : history);
            return (
              <button
                key={scope}
                type="button"
                role="tab"
                id={`tab-${scope}`}
                aria-selected={selected}
                aria-controls="appointment-list"
                onClick={() => router.replace(href({ tab: scope }), { scroll: false })}
                className={cn(
                  "h-10 rounded-[8px] px-4 text-[15px] font-semibold whitespace-nowrap",
                  selected ? "bg-surface text-ink shadow-sm" : "text-muted hover:text-ink",
                )}
              >
                {scope === "upcoming" ? T.upcomingTab(total) : T.historyTab(total)}
              </button>
            );
          })}
        </div>
        <label className="flex items-center gap-2 text-sm font-semibold whitespace-nowrap">
          {T.statusFilter}
          <select
            value={status ?? ""}
            onChange={(event) =>
              router.replace(
                href({ tab, status: (event.target.value || undefined) as AppointmentStatus }),
                { scroll: false },
              )
            }
            className={cn(inputClass(), "h-10 w-auto font-normal")}
          >
            <option value="">{T.allStatuses}</option>
            {FILTERS[tab].map((value) => (
              <option key={value} value={value}>
                {T.statuses[value]}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="grid grid-cols-1 items-start gap-5 lg:grid-cols-[minmax(0,1fr)_400px]">
        <div
          id="appointment-list"
          role="tabpanel"
          aria-labelledby={`tab-${tab}`}
          className={cn("flex min-w-0 flex-col gap-3", explicitId !== undefined && "max-lg:hidden")}
        >
          {active.isPending ? (
            <ListSkeleton />
          ) : active.isError ? (
            <div className="flex flex-col items-start gap-3">
              <Alert tone="danger">{T.loadError}</Alert>
              <Button variant="secondary" size="sm" onClick={() => void active.refetch()}>
                {TEXT.common.retry}
              </Button>
            </div>
          ) : items.length === 0 ? (
            <EmptyState tab={tab} filtered={Boolean(status)} />
          ) : (
            <>
              <ul aria-label={T.listLabel} className="flex flex-col gap-3">
                {items.map((appointment) => (
                  <AppointmentCard
                    key={appointment.id}
                    appointment={appointment}
                    selected={appointment.id === selectedId}
                    href={href({ tab, status, id: appointment.id })}
                    upcoming={tab === "upcoming"}
                    onReschedule={() => setDialog({ kind: "reschedule", appointment })}
                    onCancel={() => setDialog({ kind: "cancel", appointment })}
                  />
                ))}
              </ul>
              {active.hasNextPage ? (
                <Button
                  variant="secondary"
                  className="self-center"
                  loading={active.isFetchingNextPage}
                  onClick={() => void active.fetchNextPage()}
                >
                  {T.loadMore}
                </Button>
              ) : null}
            </>
          )}
          {tab === "upcoming" && activeCount !== undefined && activeCount > 0 ? (
            <p className="flex gap-2 rounded-[10px] bg-primary-soft px-3.5 py-3 text-sm leading-5 text-primary-ink">
              <InfoIcon size={18} className="mt-px shrink-0" />
              {T.quota(activeCount, ACTIVE_LIMIT)}
            </p>
          ) : null}
        </div>

        {selectedId !== undefined ? (
          <div className={cn("min-w-0", explicitId === undefined && "max-lg:hidden")}>
            <AppointmentDetail
              key={selectedId}
              id={selectedId}
              backHref={href({ tab, status })}
              onReschedule={(appointment) => setDialog({ kind: "reschedule", appointment })}
              onCancel={(appointment) => setDialog({ kind: "cancel", appointment })}
            />
          </div>
        ) : null}
      </div>

      {dialog?.kind === "reschedule" ? (
        <RescheduleDialog appointment={dialog.appointment} onClose={() => setDialog(null)} />
      ) : null}
      {dialog?.kind === "cancel" ? (
        <CancelDialog
          appointment={dialog.appointment}
          onClose={() => setDialog(null)}
          onCancelled={(appointment) => {
            setDialog(null);
            router.replace(href({ tab: "history", id: appointment.id }), { scroll: false });
          }}
        />
      ) : null}
    </main>
  );
}

function AppointmentCard({
  appointment,
  selected,
  href,
  upcoming,
  onReschedule,
  onCancel,
}: {
  appointment: Appointment;
  selected: boolean;
  href: string;
  upcoming: boolean;
  onReschedule: () => void;
  onCancel: () => void;
}) {
  const badge = dayBadge(appointment.start_at);
  const locked = upcoming && appointment.status === "BOOKED" && !appointment.can_change;
  return (
    <li
      className={cn(
        "flex flex-col rounded-card bg-surface",
        selected ? "border-[1.5px] border-primary" : "border border-line",
      )}
    >
      <Link
        href={href}
        replace
        scroll={false}
        aria-current={selected ? "true" : undefined}
        className="flex items-center gap-3 p-3.5 sm:gap-4 sm:p-4"
      >
        <span
          aria-hidden="true"
          className={cn(
            "flex w-14 shrink-0 flex-col items-center rounded-[10px] py-1.5 leading-tight",
            upcoming ? "bg-primary-soft text-primary-ink" : "bg-ground text-muted",
          )}
        >
          <span className="text-xs font-semibold">{badge.weekday}</span>
          <span className="text-xl font-bold">{badge.day}</span>
          <span className="text-xs">{badge.month}</span>
        </span>
        <span className="flex min-w-0 flex-1 flex-col">
          <span className="font-semibold tabular-nums">
            {formatTimeRange(appointment.start_at, appointment.end_at)}
          </span>
          <span className="truncate">{appointment.service.name}</span>
          <span className="truncate text-sm text-muted">
            {appointment.doctor.name}
            <span className="max-sm:hidden"> · {appointment.code}</span>
          </span>
        </span>
        <span className="flex shrink-0 flex-col items-end gap-1">
          <StatusBadge status={appointment.status} />
          <span className="text-xs text-muted max-sm:hidden">
            {T.bookedVia[appointment.channel]}
          </span>
        </span>
      </Link>
      {upcoming && appointment.can_change ? (
        <div className="grid grid-cols-2 gap-2 border-t border-divider p-3 lg:hidden">
          <Button variant="outline" size="sm" onClick={onReschedule}>
            {T.reschedule}
          </Button>
          <Button variant="danger" size="sm" onClick={onCancel}>
            {T.cancelShort}
          </Button>
        </div>
      ) : null}
      {locked ? (
        <p className="border-t border-divider px-4 py-2.5 text-sm text-amber-ink lg:hidden">
          {T.lockedShort(CLINIC.phone)}
        </p>
      ) : null}
    </li>
  );
}

function EmptyState({ tab, filtered }: { tab: AppointmentScope; filtered: boolean }) {
  if (filtered) return <p className="py-8 text-center text-muted">{T.emptyFiltered}</p>;
  return (
    <div className="flex flex-col items-center gap-3 rounded-card border border-dashed border-line-strong px-6 py-12 text-center">
      <span
        aria-hidden="true"
        className="flex size-12 items-center justify-center rounded-full bg-primary-soft text-primary"
      >
        <CalendarPlusIcon size={24} />
      </span>
      <p className="font-semibold">
        {tab === "upcoming" ? T.emptyUpcomingTitle : T.emptyHistoryTitle}
      </p>
      <p className="max-w-sm text-muted">
        {tab === "upcoming" ? T.emptyUpcomingBody : T.emptyHistoryBody}
      </p>
      {tab === "upcoming" ? (
        <Link href="/booking" className={buttonClass()}>
          {TEXT.nav.booking}
        </Link>
      ) : null}
    </div>
  );
}

function ListSkeleton() {
  return (
    <div aria-busy="true" aria-label={TEXT.common.loading} className="flex flex-col gap-3">
      {[0, 1, 2].map((i) => (
        <div key={i} className="flex items-center gap-4 rounded-card border border-line p-4">
          <span className="h-16 w-14 animate-pulse rounded-[10px] bg-divider" />
          <span className="flex flex-1 flex-col gap-2">
            <span className="h-4 w-24 animate-pulse rounded bg-divider" />
            <span className="h-4 w-48 animate-pulse rounded bg-divider" />
            <span className="h-3 w-32 animate-pulse rounded bg-divider" />
          </span>
        </div>
      ))}
    </div>
  );
}
