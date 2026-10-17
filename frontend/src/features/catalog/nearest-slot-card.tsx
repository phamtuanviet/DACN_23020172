"use client";

// Thẻ "Giờ trống gần nhất" nổi trên ảnh trang chủ: khung sớm nhất của mọi dịch vụ, lấy mới từ
// trình duyệt (không cache), bấm vào thì vào thẳng wizard với dịch vụ, bác sĩ, giờ đã chọn.
import Link from "next/link";

import { bookingHref } from "@/shared/availability/booking-href";
import { useEarliest } from "@/shared/availability/queries";
import { cn } from "@/shared/lib/cn";
import { clinicDay, formatDayLong, formatTime } from "@/shared/lib/datetime";
import { TEXT } from "@/shared/texts";

type ServiceInfo = { id: number; name: string; specialty: string };

export function NearestSlotCard({
  services,
  className,
}: {
  services: ServiceInfo[];
  className?: string;
}) {
  const { data, isPending, isError } = useEarliest(services.map((s) => s.id));
  const card = cn(
    "flex flex-col gap-1 rounded-card bg-surface px-[18px] py-4 shadow-[0_12px_32px_rgba(19,38,43,0.16)]",
    className,
  );
  if (isPending) {
    return (
      <div className={card} aria-hidden="true">
        <span className="h-4 w-40 animate-pulse rounded bg-divider" />
        <span className="mt-1 h-7 w-52 animate-pulse rounded bg-divider" />
        <span className="mt-1 h-4 w-44 animate-pulse rounded bg-divider" />
      </div>
    );
  }
  const earliest = isError
    ? undefined
    : [...data].sort((a, b) => a.start_at.localeCompare(b.start_at))[0];
  const service = services.find((s) => s.id === earliest?.service_id);
  if (!earliest || !service) return null;
  const day = clinicDay(earliest.start_at);
  return (
    <div className={card}>
      <span className="text-[13px] text-muted">{TEXT.home.nearestSlot(service.specialty)}</span>
      <b className="text-[22px] leading-[30px] tabular-nums">
        {formatTime(earliest.start_at)} · {formatDayLong(day)}
      </b>
      <span className="text-sm text-muted">
        {service.name} · {earliest.doctor.name}
      </span>
      <Link
        href={bookingHref({
          service: service.id,
          doctor: earliest.doctor.id,
          date: day,
          start: earliest.start_at,
        })}
        className="mt-1.5 font-semibold text-primary hover:text-primary-hover"
      >
        {TEXT.home.bookThisSlot}
      </Link>
    </div>
  );
}
