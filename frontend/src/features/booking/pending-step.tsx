"use client";

// Bước 3–4 (chọn ngày giờ, xác nhận) làm ở Sprint 3. Tạm thời giữ nguyên lựa chọn đã có trên URL
// và cho quay lại đổi bác sĩ, để các liên kết từ trang công khai (giờ trống, "Đặt giờ này") đã
// dẫn đúng chỗ ngay từ bây giờ.
import Link from "next/link";

import type { Service } from "@/shared/api/types";
import { bookingHref, type BookingState } from "@/shared/availability/booking-href";
import { TEXT } from "@/shared/texts";
import { Alert } from "@/shared/ui/alert";
import { buttonClass } from "@/shared/ui/button";

import { BookingSummary } from "./booking-summary";
import { useDoctorsOfService } from "./queries";

export function PendingStep({ service, state }: { service: Service; state: BookingState }) {
  const doctors = useDoctorsOfService(state.doctor === "any" ? undefined : service.id);
  const doctorName =
    state.doctor === "any"
      ? TEXT.booking.anyDoctor
      : doctors.data?.find((d) => d.id === state.doctor)?.name;
  return (
    <div className="flex flex-col items-start gap-6 lg:flex-row">
      <section className="flex w-full min-w-0 flex-col gap-5 rounded-card border border-line bg-surface p-[18px] md:p-7 lg:flex-1">
        <h1 className="text-2xl leading-8 font-semibold md:text-[28px] md:leading-9">
          {TEXT.booking.steps[2]}
        </h1>
        <Alert title={TEXT.booking.nextStepsTitle}>{TEXT.booking.nextStepsBody}</Alert>
        <div className="flex flex-col-reverse gap-3 border-t border-divider pt-5 sm:flex-row sm:justify-between">
          <Link
            href={bookingHref({ specialty: service.specialty.id, service: service.id })}
            className={buttonClass({ variant: "secondary" })}
          >
            {TEXT.booking.changeDoctor}
          </Link>
          <Link href="/services" className={buttonClass({ variant: "ghost" })}>
            {TEXT.catalog.showAll}
          </Link>
        </div>
      </section>
      <div className="w-full lg:w-[340px] lg:shrink-0">
        <BookingSummary service={service} doctorName={doctorName} startAt={state.start} />
      </div>
    </div>
  );
}
