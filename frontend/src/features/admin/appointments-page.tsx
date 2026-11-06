"use client";

// Lịch hẹn của quản trị (AD-appts, AD-m; UC16, FR-ADM-03): mọi lịch, lọc theo ngày, bác sĩ, trạng
// thái, kênh, tìm theo mã, tên, số điện thoại. Tab và bộ lọc nằm trên URL (?tab=queue&from=…) nên
// tải lại hay Back vẫn giữ chỗ. Máy tính: bảng; điện thoại: thẻ. Tự tải lại mỗi 60 giây (docs 9.4).
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useId, useState, type SyntheticEvent } from "react";

import type { AdminAppointment, AppointmentStatus, Channel } from "@/shared/api/types";
import { useQueueCount } from "@/shared/admin/queue";
import { cn } from "@/shared/lib/cn";
import {
  addDays,
  clinicDay,
  formatDayShort,
  formatTime,
  isValidDay,
  todayInClinic,
} from "@/shared/lib/datetime";
import { formatPhone } from "@/shared/lib/format";
import { TEXT } from "@/shared/texts";
import { Alert } from "@/shared/ui/alert";
import { StatusBadge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { inputClass } from "@/shared/ui/field";
import { ChevronRightIcon, FlagIcon, RefreshIcon, SearchIcon } from "@/shared/ui/icons";

import { AdminDialogs, AppointmentMenu, actionsOf, type AdminDialog } from "./appointment-actions";
import { PAGE_SIZE, useAdminAppointments, useAdminDoctors } from "./queries";
import { QueueTab } from "./queue-tab";

const T = TEXT.admin;
const STATUSES: AppointmentStatus[] = ["BOOKED", "ARRIVED", "COMPLETED", "CANCELLED", "NO_SHOW"];
const CHANNELS: Channel[] = ["WEB", "AGENT", "ADMIN"];
const WEEK_DAYS = 7;

type Filters = {
  from: string;
  to: string;
  doctor?: number;
  status?: AppointmentStatus;
  channel?: Channel;
  attention: boolean;
  q: string;
  page: number;
};

function readFilters(params: URLSearchParams, today: string): Filters {
  const day = (key: string, fallback: string) => {
    const value = params.get(key);
    return value && isValidDay(value) ? value : fallback;
  };
  const number = (key: string) => {
    const value = params.get(key);
    return value && /^\d+$/.test(value) ? Number(value) : undefined;
  };
  const status = params.get("status") as AppointmentStatus | null;
  const channel = params.get("channel") as Channel | null;
  return {
    from: day("from", today),
    to: day("to", addDays(today, WEEK_DAYS - 1)),
    doctor: number("doctor"),
    status: status && STATUSES.includes(status) ? status : undefined,
    channel: channel && CHANNELS.includes(channel) ? channel : undefined,
    attention: params.get("attention") === "1",
    q: params.get("q") ?? "",
    page: number("page") ?? 1,
  };
}

export function AdminAppointmentsPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const [today] = useState(todayInClinic);
  const queue = searchParams.get("tab") === "queue";
  const filters = readFilters(searchParams, today);
  const queueCount = useQueueCount().data;

  function go(next: Partial<Filters>) {
    const merged = { ...filters, page: 1, ...next };
    const query = new URLSearchParams();
    if (merged.from !== today) query.set("from", merged.from);
    if (merged.to !== addDays(today, WEEK_DAYS - 1)) query.set("to", merged.to);
    if (merged.doctor) query.set("doctor", String(merged.doctor));
    if (merged.status) query.set("status", merged.status);
    if (merged.channel) query.set("channel", merged.channel);
    if (merged.attention) query.set("attention", "1");
    if (merged.q) query.set("q", merged.q);
    if (merged.page > 1) query.set("page", String(merged.page));
    const text = query.toString();
    router.replace(text ? `${pathname}?${text}` : pathname, { scroll: false });
  }

  const tabClass = (active: boolean) =>
    cn(
      "inline-flex h-9 items-center gap-1.5 rounded-control px-3.5",
      active ? "bg-surface font-semibold text-ink shadow-sm" : "text-muted hover:text-ink",
    );

  return (
    <main className="mx-auto flex w-full max-w-[1280px] flex-col gap-4 px-4 py-6 md:px-7">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold md:text-[26px] md:leading-[34px]">
          {queue ? T.queueTitle : T.appointmentsTitle}
        </h1>
        <nav aria-label={T.tabsLabel} className="flex gap-1 rounded-[10px] bg-divider p-[3px]">
          <Link
            href={pathname}
            aria-current={!queue ? "page" : undefined}
            className={tabClass(!queue)}
          >
            {T.allTab}
          </Link>
          <Link
            href={`${pathname}?tab=queue`}
            aria-current={queue ? "page" : undefined}
            className={tabClass(queue)}
          >
            {T.queueTab}
            {queueCount ? (
              <span className="rounded-full bg-[#ffe3a8] px-1.5 text-xs leading-5 font-bold text-amber-ink">
                {queueCount}
              </span>
            ) : null}
          </Link>
        </nav>
      </div>
      {queue ? <QueueTab /> : <AllAppointments filters={filters} go={go} queueCount={queueCount} />}
    </main>
  );
}

function AllAppointments({
  filters,
  go,
  queueCount,
}: {
  filters: Filters;
  go: (next: Partial<Filters>) => void;
  queueCount: number | undefined;
}) {
  const [dialog, setDialog] = useState<AdminDialog>(null);
  const [q, setQ] = useState(filters.q);
  const [showFilters, setShowFilters] = useState(false);
  const filtersId = useId();
  const activeFilters = [filters.doctor, filters.status, filters.channel, filters.attention].filter(
    Boolean,
  ).length;
  const doctors = useAdminDoctors();
  const list = useAdminAppointments({
    dateFrom: filters.from,
    dateTo: filters.to,
    doctorId: filters.doctor,
    status: filters.status,
    channel: filters.channel,
    needsAttention: filters.attention ? true : undefined,
    q: filters.q,
    page: filters.page,
  });
  const items = list.data?.items ?? [];
  const total = list.data?.total ?? 0;
  const first = (filters.page - 1) * PAGE_SIZE + 1;
  const last = first + items.length - 1;

  function submitSearch(event: SyntheticEvent<HTMLFormElement>) {
    event.preventDefault();
    go({ q: q.trim() });
  }

  const select = inputClass(false, "sm");

  return (
    <>
      {queueCount ? (
        <Link
          href="?tab=queue"
          className="flex items-center gap-2 rounded-[10px] border border-amber-line bg-amber-soft px-3.5 py-2.5 font-semibold text-amber-ink lg:hidden"
        >
          <FlagIcon size={18} />
          <span className="flex-1">{TEXT.staff.queueCount(queueCount)}</span>
          <ChevronRightIcon size={18} />
        </Link>
      ) : null}

      <form
        role="search"
        aria-label={T.filtersLabel}
        onSubmit={submitSearch}
        className="flex flex-col gap-2 rounded-card border border-line bg-surface p-3"
      >
        <div className="flex items-center gap-2">
          <label className="flex h-10 min-w-0 flex-1 items-center gap-2 rounded-control border border-line-strong bg-surface px-3 focus-within:border-primary">
            <SearchIcon size={16} className="shrink-0 text-muted" />
            <span className="sr-only">{T.search}</span>
            <input
              type="search"
              value={q}
              maxLength={100}
              placeholder={T.searchPlaceholder}
              onChange={(event) => setQ(event.target.value)}
              className="min-w-0 flex-1 bg-transparent text-sm outline-none"
            />
          </label>
          <Button type="submit" size="sm" variant="secondary">
            {T.searchButton}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            aria-expanded={showFilters}
            aria-controls={filtersId}
            onClick={() => setShowFilters((value) => !value)}
            className="md:hidden"
          >
            {activeFilters > 0 ? T.filtersCount(activeFilters) : T.filters}
          </Button>
        </div>
        <div
          id={filtersId}
          className={cn("flex-wrap items-end gap-2", showFilters ? "flex" : "hidden md:flex")}
        >
          <label className="flex flex-col gap-1 text-xs font-semibold text-muted">
            {T.dateFrom}
            <input
              type="date"
              value={filters.from}
              onChange={(event) =>
                event.target.value &&
                go({ from: event.target.value, to: maxDay(event.target.value, filters.to) })
              }
              className={select}
            />
          </label>
          <label className="flex flex-col gap-1 text-xs font-semibold text-muted">
            {T.dateTo}
            <input
              type="date"
              value={filters.to}
              min={filters.from}
              onChange={(event) => event.target.value && go({ to: event.target.value })}
              className={select}
            />
          </label>
          <label className="flex flex-col gap-1 text-xs font-semibold text-muted">
            {T.doctor}
            <select
              value={filters.doctor ?? ""}
              onChange={(event) =>
                go({ doctor: event.target.value ? Number(event.target.value) : undefined })
              }
              className={select}
            >
              <option value="">{T.allDoctors}</option>
              {(doctors.data ?? []).map((doctor) => (
                <option key={doctor.id} value={doctor.id}>
                  {doctor.name}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs font-semibold text-muted">
            {T.status}
            <select
              value={filters.status ?? ""}
              onChange={(event) =>
                go({ status: (event.target.value || undefined) as AppointmentStatus | undefined })
              }
              className={select}
            >
              <option value="">{T.allStatuses}</option>
              {STATUSES.map((status) => (
                <option key={status} value={status}>
                  {TEXT.appointments.statuses[status]}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs font-semibold text-muted">
            {T.channel}
            <select
              value={filters.channel ?? ""}
              onChange={(event) =>
                go({ channel: (event.target.value || undefined) as Channel | undefined })
              }
              className={select}
            >
              <option value="">{T.allChannels}</option>
              {CHANNELS.map((channel) => (
                <option key={channel} value={channel}>
                  {T.channels[channel]}
                </option>
              ))}
            </select>
          </label>
          <label className="flex h-10 items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={filters.attention}
              onChange={(event) => go({ attention: event.target.checked })}
              className="size-4 accent-primary"
            />
            {T.attentionOnly}
          </label>
        </div>
      </form>

      <div className="flex items-center justify-between gap-3 text-sm text-muted">
        <span aria-live="polite">
          {list.data && total > 0 ? T.showing(first, last, total) : null}
        </span>
        <span className="flex items-center gap-1.5">
          <RefreshIcon size={14} className={list.isFetching ? "animate-spin" : undefined} />
          {list.dataUpdatedAt ? T.updatedAt(formatTime(new Date(list.dataUpdatedAt))) : null}
        </span>
      </div>

      {list.isPending ? (
        <span aria-hidden="true" className="h-64 animate-pulse rounded-card bg-divider" />
      ) : list.isError ? (
        <div className="flex flex-col items-start gap-3">
          <Alert tone="danger">{T.loadError}</Alert>
          <Button size="sm" variant="secondary" onClick={() => void list.refetch()}>
            {TEXT.common.retry}
          </Button>
        </div>
      ) : items.length === 0 ? (
        <p className="rounded-card border border-line bg-surface p-8 text-center text-muted">
          {T.empty}
        </p>
      ) : (
        <>
          <AppointmentTable items={items} onOpen={setDialog} />
          <AppointmentCards items={items} onOpen={setDialog} />
          <div className="flex justify-end gap-2">
            <Button
              size="sm"
              variant="secondary"
              disabled={filters.page <= 1}
              onClick={() => go({ page: filters.page - 1 })}
            >
              {T.prev}
            </Button>
            <Button
              size="sm"
              variant="secondary"
              disabled={last >= total}
              onClick={() => go({ page: filters.page + 1 })}
            >
              {T.next}
            </Button>
          </div>
        </>
      )}
      <AdminDialogs dialog={dialog} onClose={() => setDialog(null)} />
    </>
  );
}

function maxDay(a: string, b: string): string {
  return a > b ? a : b;
}

function When({ item }: { item: AdminAppointment }) {
  return (
    <span className="tabular-nums">
      <b>{formatDayShort(clinicDay(item.start_at))}</b> {formatTime(item.start_at)}
    </span>
  );
}

function StatusCell({ item }: { item: AdminAppointment }) {
  return (
    <span className="inline-flex flex-col items-start gap-1">
      <StatusBadge status={item.status} />
      {item.needs_attention ? (
        <span className="flex items-center gap-1 text-[13px] font-semibold text-amber">
          <FlagIcon size={14} />
          {item.attention_source ? T.attentionSources[item.attention_source] : T.needsAttention}
        </span>
      ) : null}
    </span>
  );
}

function AppointmentTable({
  items,
  onOpen,
}: {
  items: AdminAppointment[];
  onOpen: (dialog: NonNullable<AdminDialog>) => void;
}) {
  const head = "border-b border-line px-3.5 py-2.5 font-medium";
  const cell = "border-b border-divider px-3.5 py-3 align-top";
  return (
    <div className="hidden overflow-x-auto rounded-card border border-line bg-surface md:block">
      <table className="w-full min-w-[860px] border-collapse text-sm">
        <thead>
          <tr className="bg-[#f9fbfb] text-left text-muted">
            <th scope="col" className={head}>
              {T.columns.code}
            </th>
            <th scope="col" className={head}>
              {T.columns.time}
            </th>
            <th scope="col" className={head}>
              {T.columns.patient}
            </th>
            <th scope="col" className={head}>
              {T.columns.doctor}
            </th>
            <th scope="col" className={head}>
              {T.columns.channel}
            </th>
            <th scope="col" className={head}>
              {T.columns.status}
            </th>
            <th scope="col" className={head}>
              <span className="sr-only">{T.actionsFor("")}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id} className={item.needs_attention ? "bg-[#fffbf1]" : undefined}>
              <td className={cn(cell, "tabular-nums")}>{item.code}</td>
              <td className={cell}>
                <When item={item} />
              </td>
              <td className={cell}>
                {item.patient.name}
                <br />
                <span className="text-muted">{formatPhone(item.patient.phone)}</span>
              </td>
              <td className={cell}>
                {item.doctor.name}
                <br />
                <span className="text-muted">{item.service.name}</span>
              </td>
              <td className={cell}>{T.channels[item.channel]}</td>
              <td className={cell}>
                <StatusCell item={item} />
              </td>
              <td className={cn(cell, "text-right")}>
                <AppointmentMenu appointment={item} onOpen={onOpen} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AppointmentCards({
  items,
  onOpen,
}: {
  items: AdminAppointment[];
  onOpen: (dialog: NonNullable<AdminDialog>) => void;
}) {
  return (
    <ul className="flex flex-col gap-2.5 md:hidden">
      {items.map((item) => {
        const actions = actionsOf(item);
        return (
          <li
            key={item.id}
            className={cn(
              "flex flex-col gap-1.5 rounded-card border p-3.5",
              item.needs_attention ? "border-amber-line bg-[#fffbf1]" : "border-line bg-surface",
            )}
          >
            <div className="flex items-start justify-between gap-2">
              <span className="font-semibold tabular-nums">
                {formatTime(item.start_at)} · {formatDayShort(clinicDay(item.start_at))}
              </span>
              <span className="flex items-start gap-2">
                <StatusCell item={item} />
                <AppointmentMenu appointment={item} onOpen={onOpen} />
              </span>
            </div>
            <span>
              <b>{item.patient.name}</b>
              {item.patient.phone ? ` · ${formatPhone(item.patient.phone)}` : null}
            </span>
            <span className="text-sm text-muted">
              {item.doctor.name} · {item.service.name} · {T.channels[item.channel]}
            </span>
            {item.needs_attention && actions.reschedule ? (
              <div className="mt-1 flex gap-2">
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
              </div>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}
