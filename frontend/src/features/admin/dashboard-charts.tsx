// Chỉ dùng trong client component. Biểu đồ của dashboard (AD-dashboard), vẽ bằng HTML/CSS thay vì
// thư viện: cột số lịch mỗi ngày, thanh xếp chồng kênh đặt, thanh ngang số lịch theo bác sĩ. Màu theo
// token chart-1 (Web, và mọi biểu đồ một chuỗi) và chart-2 (Trợ lý); chữ luôn dùng màu chữ, không
// dùng màu của dữ liệu. Mỗi biểu đồ có dạng bảng, tooltip hiện cả khi rê chuột lẫn khi focus.
import { useRef, useState, type KeyboardEvent, type ReactNode } from "react";

import type { DayStats, DoctorStats } from "@/shared/api/types";
import { cn } from "@/shared/lib/cn";
import { formatDayLong } from "@/shared/lib/datetime";
import { formatCount, formatPercent } from "@/shared/lib/format";
import { TEXT } from "@/shared/texts";

import { niceTicks, peakIndex, showDayLabel } from "./dashboard-data";

const D = TEXT.dashboard;
const TOP_DOCTORS = 8;

/** Khung chung: tiêu đề, nút chuyển dạng bảng, chú thích cách tính. */
export function ChartCard({
  title,
  note,
  table,
  className,
  children,
}: {
  title: string;
  note?: string;
  table?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  const [asTable, setAsTable] = useState(false);
  return (
    <section
      aria-label={title}
      className={cn(
        "flex min-w-0 flex-col gap-3 rounded-card border border-line bg-surface p-4 md:p-5",
        className,
      )}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h2 className="text-base leading-6 font-semibold">{title}</h2>
        {table ? (
          <button
            type="button"
            aria-pressed={asTable}
            onClick={() => setAsTable((value) => !value)}
            className="text-sm font-semibold text-primary hover:text-primary-hover"
          >
            {asTable ? D.showChart : D.showTable}
          </button>
        ) : null}
      </div>
      {asTable ? table : children}
      {note ? <p className="text-sm text-muted">{note}</p> : null}
    </section>
  );
}

function Tooltip({ title, value, detail }: { title: string; value: string; detail?: string }) {
  return (
    <span className="flex w-max max-w-[240px] flex-col rounded-[8px] border border-line bg-surface px-3 py-2 text-left shadow-md">
      <span className="text-xs text-muted">{title}</span>
      <span className="text-[15px] font-semibold">{value}</span>
      {detail ? <span className="text-xs text-muted">{detail}</span> : null}
    </span>
  );
}

function breakdown(item: { completed: number; no_show: number; cancelled: number }): string {
  return D.dayBreakdown(item.completed, item.no_show, item.cancelled);
}

// ---------------------------------------------------------------------------- số lịch mỗi ngày
/** Cột số lịch mỗi ngày (không gồm lịch hủy). Một chuỗi nên không có chú giải; ghi số trực tiếp ở
 *  cột cao nhất, các cột khác đọc qua trục, tooltip hoặc dạng bảng. Mũi tên trái/phải chuyển cột. */
export function DailyChart({ days }: { days: DayStats[] }) {
  const [active, setActive] = useState<number | null>(null);
  const [focusIndex, setFocusIndex] = useState(days.length - 1);
  const columns = useRef<(HTMLSpanElement | null)[]>([]);
  const ticks = niceTicks(Math.max(0, ...days.map((day) => day.total)));
  const top = ticks.at(-1) ?? 1;
  const peak = peakIndex(days);
  const peakDay = days[peak];
  const height = (value: number) => `${(value / top) * 100}%`;

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const moves: Record<string, number> = {
      ArrowLeft: focusIndex - 1,
      ArrowRight: focusIndex + 1,
      Home: 0,
      End: days.length - 1,
    };
    const next = moves[event.key];
    if (next === undefined) return;
    event.preventDefault();
    const index = Math.min(days.length - 1, Math.max(0, next));
    setFocusIndex(index);
    columns.current[index]?.focus();
  }

  const shown = active === null ? undefined : days[active];
  return (
    <div className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-2">
      <div
        aria-hidden="true"
        className="relative h-44 w-8 text-right text-xs text-muted tabular-nums"
      >
        {ticks.map((tick) => (
          <span
            key={tick}
            className="absolute right-0 translate-y-1/2 leading-none"
            style={{ bottom: height(tick) }}
          >
            {formatCount(tick)}
          </span>
        ))}
      </div>
      <div className="relative h-44">
        {ticks.map((tick) => (
          <span
            key={tick}
            aria-hidden="true"
            className={cn("absolute inset-x-0 h-px", tick === 0 ? "bg-line" : "bg-divider")}
            style={{ bottom: height(tick) }}
          />
        ))}
        <div
          role="group"
          aria-label={peakDay ? D.dailyLabel(peakDay.total, formatDayLong(peakDay.day)) : D.empty}
          onKeyDown={onKeyDown}
          onMouseLeave={() => setActive(null)}
          className="absolute inset-0 flex items-end"
        >
          {days.map((day, index) => (
            <span
              key={day.day}
              ref={(node) => {
                columns.current[index] = node;
              }}
              role="img"
              aria-label={`${formatDayLong(day.day)}: ${D.dayReadout(day.total)}, ${breakdown(day)}`}
              tabIndex={index === focusIndex ? 0 : -1}
              onMouseEnter={() => setActive(index)}
              onFocus={() => {
                setActive(index);
                setFocusIndex(index);
              }}
              onBlur={() => setActive(null)}
              className={cn(
                "relative flex h-full min-w-0 flex-1 items-end justify-center rounded-t-[4px] outline-offset-0",
                active === index && "bg-primary-soft/70",
              )}
            >
              {day.total > 0 ? (
                <span
                  className="w-[min(24px,62%)] rounded-t-[4px] bg-chart-1"
                  style={{ height: height(day.total) }}
                />
              ) : null}
              {index === peak ? (
                <span
                  aria-hidden="true"
                  className="absolute text-xs font-semibold"
                  style={{ bottom: `calc(${height(day.total)} + 4px)` }}
                >
                  {formatCount(day.total)}
                </span>
              ) : null}
            </span>
          ))}
        </div>
        {shown && active !== null ? (
          <span
            aria-hidden="true"
            className="pointer-events-none absolute top-0 z-10"
            style={
              active < days.length / 2
                ? { left: `calc(${((active + 1) / days.length) * 100}% + 6px)` }
                : { right: `calc(${((days.length - active) / days.length) * 100}% + 6px)` }
            }
          >
            <Tooltip
              title={formatDayLong(shown.day)}
              value={D.dayReadout(shown.total)}
              detail={breakdown(shown)}
            />
          </span>
        ) : null}
      </div>
      <span />
      <div aria-hidden="true" className="flex pt-1.5 text-xs text-muted tabular-nums">
        {days.map((day, index) => (
          <span key={day.day} className="min-w-0 flex-1 text-center">
            {showDayLabel(index, days.length) ? day.day.slice(8) : ""}
          </span>
        ))}
      </div>
    </div>
  );
}

export function DailyTable({ days }: { days: DayStats[] }) {
  const C = D.columns;
  return (
    <div className="overflow-x-auto rounded-[8px] border border-divider">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-ground text-left text-muted">
          <tr>
            <th className="px-3 py-2 font-semibold">{C.day}</th>
            <th className="px-3 py-2 text-right font-semibold">{C.total}</th>
            <th className="px-3 py-2 text-right font-semibold">{C.completed}</th>
            <th className="px-3 py-2 text-right font-semibold">{C.noShow}</th>
            <th className="px-3 py-2 text-right font-semibold">{C.cancelled}</th>
          </tr>
        </thead>
        <tbody className="tabular-nums">
          {days.map((day) => (
            <tr key={day.day} className="border-t border-divider">
              <th scope="row" className="px-3 py-1.5 text-left font-normal">
                {formatDayLong(day.day)}
              </th>
              <td className="px-3 py-1.5 text-right font-semibold">{day.total}</td>
              <td className="px-3 py-1.5 text-right">{day.completed}</td>
              <td className="px-3 py-1.5 text-right">{day.no_show}</td>
              <td className="px-3 py-1.5 text-right">{day.cancelled}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------- kênh đặt
/** Tỷ lệ đặt qua web và trợ lý: thanh xếp chồng, khe 2px giữa hai phần; chú giải kèm số lịch và
 *  tỷ lệ nên mọi giá trị đều đọc được không cần rê chuột. */
export function ChannelSplit({ web, agent }: { web: number; agent: number }) {
  const [active, setActive] = useState<string | null>(null);
  const total = web + agent;
  if (total === 0) return <p className="text-sm text-muted">{D.noBookings}</p>;
  const parts = [
    { key: "web", label: D.channels.web, value: web, color: "bg-chart-1" },
    { key: "agent", label: D.channels.agent, value: agent, color: "bg-chart-2" },
  ];
  const visible = parts.filter((part) => part.value > 0);
  return (
    <div className="flex flex-col gap-3" onMouseLeave={() => setActive(null)}>
      <div
        role="img"
        aria-label={D.channelLabel(formatPercent(web / total), formatPercent(agent / total))}
        className="flex h-4 gap-[2px]"
      >
        {visible.map((part, index) => (
          <span
            key={part.key}
            onMouseEnter={() => setActive(part.key)}
            className={cn(
              "h-full min-w-[4px] transition-opacity",
              part.color,
              index === 0 && "rounded-l-[4px]",
              index === visible.length - 1 && "rounded-r-[4px]",
              active && active !== part.key && "opacity-40",
            )}
            style={{ flexGrow: part.value, flexBasis: 0 }}
          />
        ))}
      </div>
      <dl className="grid grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-x-4 gap-y-2 text-sm">
        {parts.map((part) => (
          <div
            key={part.key}
            onMouseEnter={() => setActive(part.key)}
            className={cn("contents", active && active !== part.key && "[&>*]:opacity-60")}
          >
            <dt className="flex items-center gap-2">
              <span
                aria-hidden="true"
                className={cn("size-3 shrink-0 rounded-[3px]", part.color)}
              />
              {part.label}
            </dt>
            <dd className="text-right text-muted tabular-nums">{D.bookings(part.value)}</dd>
            <dd className="text-right font-semibold tabular-nums">
              {formatPercent(part.value / total)}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

// ---------------------------------------------------------------------------- theo bác sĩ
/** Số lịch theo bác sĩ (không gồm lịch hủy), nhiều nhất trước: mọi thanh cùng màu chart-1 vì bác
 *  sĩ là danh mục không thứ tự; số ghi ở đầu thanh. Mặc định hiện 8 bác sĩ. */
export function DoctorBars({ doctors }: { doctors: DoctorStats[] }) {
  const [showAll, setShowAll] = useState(false);
  const [active, setActive] = useState<number | null>(null);
  const max = Math.max(1, ...doctors.map((doctor) => doctor.total));
  const shown = showAll ? doctors : doctors.slice(0, TOP_DOCTORS);
  return (
    <div className="flex flex-col gap-2">
      <ul className="flex flex-col gap-1" onMouseLeave={() => setActive(null)}>
        {shown.map((doctor) => (
          <li
            key={doctor.id}
            tabIndex={0}
            aria-label={`${doctor.name}: ${D.dayReadout(doctor.total)}, ${breakdown(doctor)}`}
            onMouseEnter={() => setActive(doctor.id)}
            onFocus={() => setActive(doctor.id)}
            onBlur={() => setActive(null)}
            className={cn(
              "relative grid grid-cols-1 gap-x-3 gap-y-1 rounded-[8px] px-2 py-1.5 md:grid-cols-[minmax(0,13rem)_minmax(0,1fr)] md:items-center",
              active === doctor.id && "bg-ground",
            )}
          >
            <span aria-hidden="true" className="truncate text-sm">
              {doctor.name}
            </span>
            <span aria-hidden="true" className="flex items-center gap-2">
              {doctor.total > 0 ? (
                <span
                  className="h-3 rounded-r-[4px] bg-chart-1"
                  style={{ width: `calc((100% - 2.5rem) * ${doctor.total / max})` }}
                />
              ) : null}
              <span className="text-sm font-semibold tabular-nums">{doctor.total}</span>
            </span>
            {active === doctor.id ? (
              <span
                aria-hidden="true"
                className="pointer-events-none absolute right-2 bottom-full z-10 translate-y-1"
              >
                <Tooltip
                  title={doctor.name}
                  value={D.dayReadout(doctor.total)}
                  detail={breakdown(doctor)}
                />
              </span>
            ) : null}
          </li>
        ))}
      </ul>
      {doctors.length > TOP_DOCTORS ? (
        <button
          type="button"
          aria-expanded={showAll}
          onClick={() => setShowAll((value) => !value)}
          className="self-start text-sm font-semibold text-primary hover:text-primary-hover"
        >
          {showAll ? D.showTopDoctors : D.showAllDoctors(doctors.length)}
        </button>
      ) : null}
    </div>
  );
}

export function DoctorTable({ doctors }: { doctors: DoctorStats[] }) {
  const C = D.columns;
  return (
    <div className="overflow-x-auto rounded-[8px] border border-divider">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-ground text-left text-muted">
          <tr>
            <th className="px-3 py-2 font-semibold">{C.doctor}</th>
            <th className="px-3 py-2 text-right font-semibold">{C.total}</th>
            <th className="px-3 py-2 text-right font-semibold">{C.completed}</th>
            <th className="px-3 py-2 text-right font-semibold">{C.noShow}</th>
            <th className="px-3 py-2 text-right font-semibold">{C.cancelled}</th>
          </tr>
        </thead>
        <tbody className="tabular-nums">
          {doctors.map((doctor) => (
            <tr key={doctor.id} className="border-t border-divider">
              <th scope="row" className="px-3 py-1.5 text-left font-normal">
                {doctor.name}
              </th>
              <td className="px-3 py-1.5 text-right font-semibold">{doctor.total}</td>
              <td className="px-3 py-1.5 text-right">{doctor.completed}</td>
              <td className="px-3 py-1.5 text-right">{doctor.no_show}</td>
              <td className="px-3 py-1.5 text-right">{doctor.cancelled}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
