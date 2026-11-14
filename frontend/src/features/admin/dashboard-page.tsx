"use client";

// Tổng quan của quản trị (AD-dashboard; UC19, FR-RPT-01, AC-18): số lịch hôm nay và trong khoảng,
// tỷ lệ hủy, tỷ lệ vắng mặt so với kỳ trước, số lịch mỗi ngày, kênh đặt web và trợ lý, số lịch theo
// bác sĩ, việc cần xử lý. Khoảng thời gian nằm trên URL (?days=7|14|30) và áp cho mọi số liệu bên
// dưới; đổi khoảng thì giữ số cũ (mờ đi) tới khi có số mới. Tự tải lại mỗi 60 giây (docs mục 9.4).
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState, type ReactNode } from "react";

import type { Stats } from "@/shared/api/types";
import { useQueueCount } from "@/shared/admin/queue";
import { cn } from "@/shared/lib/cn";
import { todayInClinic } from "@/shared/lib/datetime";
import { formatCount, formatPercent, formatRating } from "@/shared/lib/format";
import { TEXT } from "@/shared/texts";
import { Alert } from "@/shared/ui/alert";
import { Button, buttonClass } from "@/shared/ui/button";
import { inputClass } from "@/shared/ui/field";
import { ArrowDownIcon, ArrowUpIcon, FlagIcon } from "@/shared/ui/icons";

import {
  ChannelSplit,
  ChartCard,
  DailyChart,
  DailyTable,
  DoctorBars,
  DoctorTable,
} from "./dashboard-charts";
import { DEFAULT_PERIOD, PERIODS, parsePeriod, periodRange, rateDelta } from "./dashboard-data";
import { useAdminStats } from "./queries";

const D = TEXT.dashboard;

export function AdminDashboardPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const [today] = useState(todayInClinic);
  const days = parsePeriod(searchParams.get("days"));
  const stats = useAdminStats(periodRange(today, days));

  function choose(value: string) {
    const period = parsePeriod(value);
    router.replace(period === DEFAULT_PERIOD ? pathname : `${pathname}?days=${period}`, {
      scroll: false,
    });
  }

  return (
    <main className="mx-auto flex w-full max-w-[1280px] flex-col gap-4 px-4 py-6 md:px-7">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold md:text-[26px] md:leading-[34px]">{D.title}</h1>
        <label className="flex items-center gap-2 text-sm font-semibold whitespace-nowrap">
          {D.period}
          <select
            value={days}
            onChange={(event) => choose(event.target.value)}
            className={cn(inputClass(false, "sm"), "w-auto font-normal")}
          >
            {PERIODS.map((period) => (
              <option key={period} value={period}>
                {D.periods[period]}
              </option>
            ))}
          </select>
        </label>
      </div>

      {stats.isPending ? (
        <DashboardSkeleton />
      ) : stats.isError ? (
        <div className="flex flex-col items-start gap-3">
          <Alert tone="danger">{D.loadError}</Alert>
          <Button variant="secondary" size="sm" onClick={() => void stats.refetch()}>
            {TEXT.common.retry}
          </Button>
        </div>
      ) : (
        <div
          aria-busy={stats.isPlaceholderData}
          className={cn(
            "flex flex-col gap-4 transition-opacity",
            stats.isPlaceholderData && "opacity-60",
          )}
        >
          <Overview stats={stats.data} days={days} today={today} />
        </div>
      )}
    </main>
  );
}

function Overview({ stats, days, today }: { stats: Stats; days: number; today: string }) {
  const todayStats = stats.days.find((day) => day.day === today);
  const totals = stats.totals;
  return (
    <>
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        <StatTile
          label={D.today}
          value={formatCount(todayStats?.total ?? 0)}
          sub={D.todaySub(
            todayStats?.completed ?? 0,
            (todayStats?.booked ?? 0) + (todayStats?.arrived ?? 0),
          )}
        />
        <StatTile
          label={D.inPeriod(days)}
          value={formatCount(totals.total)}
          sub={D.inPeriodSub(totals.completed, totals.no_show)}
        />
        <RateTile
          label={D.cancelRate(days)}
          current={stats.rates.cancel_rate}
          previous={stats.previous_rates.cancel_rate}
          days={days}
        />
        <RateTile
          label={D.noShowRate(days)}
          current={stats.rates.no_show_rate}
          previous={stats.previous_rates.no_show_rate}
          days={days}
        />
      </div>
      <p className="-mt-1 text-sm text-muted">{D.rateNote}</p>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <ChartCard
          title={D.dailyTitle(days)}
          note={D.dailyNote}
          table={<DailyTable days={stats.days} />}
        >
          {totals.total + totals.cancelled > 0 ? (
            <DailyChart key={days} days={stats.days} />
          ) : (
            <p className="py-10 text-center text-sm text-muted">{D.empty}</p>
          )}
        </ChartCard>
        <ChartCard title={D.channelTitle(days)} note={D.channelNote}>
          <ChannelSplit web={stats.channels.web} agent={stats.channels.agent} />
        </ChartCard>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <ChartCard
          title={D.doctorsTitle(days)}
          note={D.doctorsNote}
          table={<DoctorTable doctors={stats.doctors} />}
        >
          <DoctorBars doctors={stats.doctors} />
        </ChartCard>
        <QueueCard />
      </div>
    </>
  );
}

function StatTile({ label, value, sub }: { label: string; value: string; sub: ReactNode }) {
  return (
    <section
      aria-label={label}
      className="flex min-w-0 flex-col gap-1 rounded-card border border-line bg-surface p-3.5 md:p-4"
    >
      <h2 className="text-sm text-muted">{label}</h2>
      <p className="text-2xl leading-8 font-semibold md:text-[28px] md:leading-9">{value}</p>
      <p className="text-sm text-muted">{sub}</p>
    </section>
  );
}

/** Tỷ lệ hủy, vắng mặt: tăng là xấu (đỏ, mũi tên lên), giảm là tốt (xanh, mũi tên xuống). */
function RateTile({
  label,
  current,
  previous,
  days,
}: {
  label: string;
  current: number | null;
  previous: number | null;
  days: number;
}) {
  const delta = rateDelta(current, previous);
  let sub: ReactNode = D.deltaNone;
  if (delta?.direction === "same") sub = D.deltaSame(days);
  else if (delta) {
    const up = delta.direction === "up";
    const Arrow = up ? ArrowUpIcon : ArrowDownIcon;
    sub = (
      <span className={cn("inline-flex items-start gap-1", up ? "text-danger" : "text-success")}>
        <Arrow size={16} className="mt-0.5 shrink-0" />
        {D.delta(delta.direction, formatRating(delta.points), days)}
      </span>
    );
  }
  return (
    <StatTile
      label={label}
      value={current === null ? D.noRate : formatPercent(current)}
      sub={sub}
    />
  );
}

function QueueCard() {
  const count = useQueueCount().data;
  return (
    <section
      aria-label={D.queueTitle}
      className="flex flex-col gap-3 rounded-card border border-line bg-surface p-4 md:p-5"
    >
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-base leading-6 font-semibold">{D.queueTitle}</h2>
        {count ? (
          <span className="rounded-full bg-[#ffe3a8] px-2 text-sm leading-6 font-bold text-amber-ink">
            {count}
          </span>
        ) : null}
      </div>
      {count === undefined ? (
        <span aria-hidden="true" className="h-10 animate-pulse rounded bg-divider" />
      ) : count > 0 ? (
        <p className="flex gap-2 text-[15px]">
          <FlagIcon size={18} className="mt-0.5 shrink-0 text-amber" />
          {D.queueBody(count)}
        </p>
      ) : (
        <p className="text-[15px] text-muted">{D.queueEmpty}</p>
      )}
      <Link
        href="/admin/appointments?tab=queue"
        className={buttonClass({ variant: "outline", size: "sm", className: "self-start" })}
      >
        {D.openQueue}
      </Link>
    </section>
  );
}

function DashboardSkeleton() {
  return (
    <div aria-busy="true" aria-label={TEXT.common.loading} className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <span key={i} className="h-[118px] animate-pulse rounded-card bg-divider" />
        ))}
      </div>
      <span className="h-72 animate-pulse rounded-card bg-divider" />
    </div>
  );
}
