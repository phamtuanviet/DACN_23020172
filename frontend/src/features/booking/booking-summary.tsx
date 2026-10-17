// Khung "Lịch hẹn của bạn" bên cạnh các bước (P-book-2): dịch vụ, bác sĩ, thời gian, giá.
import type { Service } from "@/shared/api/types";
import { formatDateTime } from "@/shared/lib/datetime";
import { formatDuration, formatPrice } from "@/shared/lib/format";
import { TEXT } from "@/shared/texts";

export function BookingSummary({
  service,
  doctorName,
  startAt,
}: {
  service?: Service;
  doctorName?: string;
  startAt?: string;
}) {
  const rows: [string, string][] = [
    [
      TEXT.booking.summaryService,
      service
        ? `${service.name} · ${formatDuration(service.duration_min)}`
        : TEXT.booking.notChosen,
    ],
    [TEXT.booking.summaryDoctor, doctorName ?? TEXT.booking.notChosen],
    [TEXT.booking.summaryTime, startAt ? formatDateTime(startAt) : TEXT.booking.notChosen],
    [
      TEXT.booking.summaryPrice,
      service
        ? `${formatPrice(service.ref_price_vnd)} · ${TEXT.booking.payAtClinic}`
        : TEXT.booking.notChosen,
    ],
  ];
  return (
    <aside
      aria-label={TEXT.booking.summaryTitle}
      className="flex flex-col gap-3 rounded-card border border-line bg-surface p-5 lg:sticky lg:top-24"
    >
      <h2 className="text-lg font-semibold">{TEXT.booking.summaryTitle}</h2>
      <dl className="flex flex-col gap-2.5 text-[15px] leading-[22px]">
        {rows.map(([label, value]) => (
          <div key={label} className="flex flex-col gap-0.5 border-t border-divider pt-2.5">
            <dt className="text-sm text-muted">{label}</dt>
            <dd className={value === TEXT.booking.notChosen ? "text-muted" : "font-medium"}>
              {value}
            </dd>
          </div>
        ))}
      </dl>
    </aside>
  );
}
