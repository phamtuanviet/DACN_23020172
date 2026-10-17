"use client";

// Wizard đặt lịch (UC05): dịch vụ → bác sĩ → ngày giờ → xác nhận. Bước hiện tại suy ra từ URL
// (docs mục 9.3), nên nút Quay lại của trình duyệt và liên kết từ trang công khai luôn đúng bước.
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { bookingHref } from "@/shared/availability/booking-href";
import { TEXT } from "@/shared/texts";
import { Alert } from "@/shared/ui/alert";
import { buttonClass } from "@/shared/ui/button";
import { Stepper } from "@/shared/ui/stepper";

import { DoctorStep } from "./doctor-step";
import { currentStep, parseBookingParams } from "./params";
import { PendingStep } from "./pending-step";
import { useDoctorsOfService, useServices } from "./queries";
import { ServiceStep } from "./service-step";

export function BookingWizard() {
  const searchParams = useSearchParams();
  const state = parseBookingParams(searchParams);
  const step = currentStep(state);
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
  } else {
    content = <PendingStep service={service} state={state} />;
  }

  return (
    <main className="mx-auto flex w-full max-w-[1200px] flex-col gap-6 px-4 pt-6 pb-28 md:px-6">
      <Stepper
        label="Các bước đặt lịch"
        steps={[...TEXT.booking.steps]}
        current={step}
        details={[service?.name, doctorName]}
      />
      {content}
    </main>
  );
}
