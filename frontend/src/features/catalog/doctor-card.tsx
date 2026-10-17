// Thẻ bác sĩ dùng ở trang chủ, trang Dịch vụ và bác sĩ, mục "Bác sĩ khác cùng chuyên khoa".
import Link from "next/link";

import type { Doctor } from "@/shared/api/types";
import { EarliestHint } from "@/shared/availability/earliest-hint";
import { cn } from "@/shared/lib/cn";
import { TEXT } from "@/shared/texts";
import { Avatar } from "@/shared/ui/avatar";

/** Dịch vụ dùng để tính "Sớm nhất": dịch vụ đang chọn nếu bác sĩ có làm, không thì dịch vụ đầu. */
export function earliestServiceOf(doctor: Doctor, preferred?: number): number | undefined {
  if (preferred !== undefined && doctor.services.some((s) => s.id === preferred)) return preferred;
  return doctor.services[0]?.id;
}

export function DoctorCard({
  doctor,
  serviceIds,
  preferredServiceId,
  layout = "stack",
  className,
}: {
  doctor: Doctor;
  /** Mọi dịch vụ tính "Sớm nhất" trên trang, để các thẻ dùng chung một request. */
  serviceIds: number[];
  preferredServiceId?: number;
  layout?: "stack" | "row";
  className?: string;
}) {
  const serviceId = earliestServiceOf(doctor, preferredServiceId);
  const gender = TEXT.doctor.genders[doctor.gender];
  return (
    <Link
      href={`/doctors/${doctor.id}`}
      className={cn(
        "flex rounded-card border border-line bg-surface text-ink transition-colors hover:border-primary",
        layout === "stack" ? "flex-col gap-1.5 p-[18px]" : "items-center gap-3.5 p-4",
        className,
      )}
    >
      <Avatar
        id={doctor.id}
        name={doctor.name}
        size={layout === "stack" ? "lg" : "md"}
        className={layout === "stack" ? "mb-1.5" : undefined}
      />
      <span className="flex min-w-0 flex-1 flex-col gap-0.5">
        <b className="text-[17px] font-semibold">{doctor.name}</b>
        <span className="text-sm text-muted">
          {doctor.specialty.name} · {gender}
        </span>
        {serviceId !== undefined ? (
          <span
            className={cn("text-sm", layout === "stack" && "mt-1.5 border-t border-divider pt-2.5")}
          >
            <EarliestHint
              serviceIds={serviceIds}
              serviceId={serviceId}
              doctorId={doctor.id}
              label={TEXT.catalog.earliestLabel}
            />
          </span>
        ) : null}
      </span>
    </Link>
  );
}
