// Thẻ dịch vụ ở trang Dịch vụ và bác sĩ (G-services): giá, thời lượng, phạm vi khám, bác sĩ thực
// hiện và giờ sớm nhất; nút Đặt lịch dẫn thẳng vào bước chọn bác sĩ.
import Link from "next/link";

import type { Service } from "@/shared/api/types";
import { bookingHref } from "@/shared/availability/booking-href";
import { EarliestHint } from "@/shared/availability/earliest-hint";
import { formatDuration, formatPrice, splitScope } from "@/shared/lib/format";
import { TEXT } from "@/shared/texts";
import { Avatar } from "@/shared/ui/avatar";
import { buttonClass } from "@/shared/ui/button";
import { ChevronDownIcon } from "@/shared/ui/icons";

export function ServiceCard({
  service,
  serviceIds,
  scopeOpen = false,
}: {
  service: Service;
  serviceIds: number[];
  scopeOpen?: boolean;
}) {
  const scope = splitScope(service.scope_description);
  const doctors = service.doctors;
  return (
    <article className="flex flex-col gap-3 rounded-card border border-line bg-surface px-5 py-[18px]">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="flex flex-col gap-1">
          <h3 className="text-[19px] leading-[26px] font-semibold">{service.name}</h3>
          <span className="text-sm text-muted">
            {service.specialty.name} · {formatDuration(service.duration_min)}
          </span>
        </div>
        <b className="text-lg tabular-nums">{formatPrice(service.ref_price_vnd)}</b>
      </div>
      <details open={scopeOpen} className="group rounded-[10px] bg-ground">
        <summary className="flex cursor-pointer list-none justify-between gap-3 px-3.5 py-2.5 text-[15px] font-semibold [&::-webkit-details-marker]:hidden">
          {TEXT.catalog.scope}
          <ChevronDownIcon
            size={18}
            className="shrink-0 text-muted transition-transform group-open:rotate-180"
          />
        </summary>
        <div className="flex flex-col gap-1.5 px-3.5 pb-3 text-[15px] leading-[22px] text-subtle">
          <span>{scope.included}</span>
          {scope.excluded ? (
            <span>
              <b className="text-ink">{TEXT.catalog.excluded}</b> {scope.excluded}
            </span>
          ) : null}
        </div>
      </details>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-3 pt-1 max-md:flex-col max-md:items-stretch">
        <span className="flex items-center gap-2.5 text-sm text-muted">
          {doctors.length > 0 ? (
            <span aria-hidden="true" className="flex">
              {doctors.slice(0, 3).map((doctor, index) => (
                <Avatar
                  key={doctor.id}
                  id={doctor.id}
                  name={doctor.name}
                  size="xs"
                  className={index > 0 ? "-ml-2 ring-2 ring-surface" : "ring-2 ring-surface"}
                />
              ))}
            </span>
          ) : null}
          <span>
            {doctors.length > 0 ? (
              <>
                {TEXT.catalog.doctorCount(doctors.length)} ·{" "}
                <span className="text-ink">
                  <EarliestHint serviceIds={serviceIds} serviceId={service.id} />
                </span>
              </>
            ) : (
              TEXT.catalog.noDoctor
            )}
          </span>
        </span>
        {doctors.length > 0 ? (
          <Link
            href={bookingHref({ specialty: service.specialty.id, service: service.id })}
            className={buttonClass({ className: "md:ml-auto" })}
          >
            {TEXT.catalog.book}
          </Link>
        ) : null}
      </div>
    </article>
  );
}
