"use client";

// Wizard đặt lịch (UC05): dịch vụ → bác sĩ → ngày giờ → xác nhận. Bước hiện tại suy ra từ URL
// (docs mục 9.3), nên nút Quay lại của trình duyệt và liên kết từ trang công khai luôn đúng bước.
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";

import { bookingHref } from "@/shared/availability/booking-href";
import { formatSlotLong } from "@/shared/lib/datetime";
import { TEXT } from "@/shared/texts";
import { Alert } from "@/shared/ui/alert";
import { buttonClass } from "@/shared/ui/button";
import { Stepper } from "@/shared/ui/stepper";

import { ConfirmStep } from "./confirm-step";
import { DateTimeStep } from "./datetime-step";
import { DoctorStep } from "./doctor-step";
import { currentStep, parseBookingParams } from "./params";
import { useDoctorsOfService, useServices } from "./queries";
import { ServiceStep } from "./service-step";

export function BookingWizard() {
  const searchParams = useSearchParams();
  const state = parseBookingParams(searchParams);
  const step = currentStep(state);
  // Lý do khám chỉ nằm trong bộ nhớ (dữ liệu sức khỏe): wizard không remount khi đổi bước vì
  // chỉ query trên URL thay đổi, nên giá trị còn nguyên giữa bước 3 và bước 4.
  const [reason, setReason] = useState("");
  const services = useServices({}, step > 0);
  const service = services.data?.find((s) => s.id === state.service);
  const doctors = useDoctorsOfService(
    step > 1 && state.doctor !== "any" ? state.service : undefined,
  );
  const doctorName =
    state.doctor === "any"
      ? TEXT.booking.anyDoctor
      : doctors.data?.find((d) => d.id === state.doctor)?.name;

  let content;
  if (step === 0) {
    content = <ServiceStep state={state} />;
  } else if (services.isPending) {
    content = <span aria-hidden="true" className="h-80 animate-pulse rounded-card bg-divider" />;
  } else if (!service) {
    content = (
      <div className="flex flex-col items-start gap-3">
        <Alert tone="warning">
          {services.isError ? TEXT.common.genericError : TEXT.booking.serviceMissing}
        </Alert>
        <Link href={bookingHref({})} className={buttonClass({ variant: "secondary" })}>
          {TEXT.booking.back}
        </Link>
      </div>
    );
  } else if (step === 1) {
    content = <DoctorStep key={service.id} service={service} />;
  } else if (step === 2) {
    content = (
      <DateTimeStep
        key={`${service.id}-${state.doctor}`}
        service={service}
        state={state}
        doctorName={doctorName}
        reason={reason}
        onReasonChange={setReason}
      />
    );
  } else {
    content = (
      <ConfirmStep
        service={service}
        state={state}
        startAt={state.start ?? ""}
        doctorName={doctorName}
        reason={reason}
        onBooked={() => setReason("")}
      />
    );
  }

  return (
    <main className="mx-auto flex w-full max-w-[1200px] flex-col gap-6 px-4 pt-6 pb-28 md:px-6">
      <Stepper
        label="Các bước đặt lịch"
        steps={[...TEXT.booking.steps]}
        current={step}
        details={[service?.name, doctorName, state.start ? formatSlotLong(state.start) : undefined]}
      />
      {content}
    </main>
  );
}
