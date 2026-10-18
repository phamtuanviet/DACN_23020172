// Chỉ dùng trong client component. Hộp thoại đổi lịch (P-dialogs, UC06): cùng dịch vụ, mặc định
// cùng bác sĩ, chọn được bác sĩ khác; so sánh lịch cũ → mới trước khi xác nhận. Khung vừa bị đặt
// thì lịch cũ giữ nguyên (AC-04) và danh sách giờ trống tải lại.
import { useState } from "react";

import { errorMessage, toApiError } from "@/shared/api/errors";
import type { Appointment, AvailabilitySlot } from "@/shared/api/types";
import { useRescheduleAppointment } from "@/shared/appointments/queries";
import { useAvailability, useDoctorsOfService } from "@/shared/availability/queries";
import { SlotPicker } from "@/shared/availability/slot-picker";
import { cn } from "@/shared/lib/cn";
import {
  addDays,
  formatDayLong,
  formatDayShort,
  formatSlot,
  formatSlotLong,
  todayInClinic,
} from "@/shared/lib/datetime";
import { TEXT } from "@/shared/texts";
import { Alert } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Dialog } from "@/shared/ui/dialog";
import { inputClass } from "@/shared/ui/field";
import { toast } from "@/shared/ui/toast";

const T = TEXT.appointments;
const RANGE_DAYS = 14;

export function RescheduleDialog({
  appointment,
  onClose,
}: {
  appointment: Appointment;
  onClose: () => void;
}) {
  const [today] = useState(todayInClinic);
  const [doctorId, setDoctorId] = useState(appointment.doctor.id);
  const [pickedDay, setPickedDay] = useState<string | null>(null);
  const [slot, setSlot] = useState<AvailabilitySlot | null>(null);
  const doctors = useDoctorsOfService(appointment.service.id);
  const availability = useAvailability({
    serviceId: appointment.service.id,
    doctorId,
    dateFrom: today,
    dateTo: addDays(today, RANGE_DAYS - 1),
  });
  const reschedule = useRescheduleAppointment();
  const error = reschedule.error ? toApiError(reschedule.error) : null;

  const days = availability.data?.days ?? [];
  const day =
    days.find((d) => d.date === pickedDay && d.status === "OPEN") ??
    days.find((d) => d.status === "OPEN");
  const others = (doctors.data ?? []).filter((d) => d.id !== appointment.doctor.id);

  function changeDoctor(id: number) {
    setDoctorId(id);
    setPickedDay(null);
    setSlot(null);
    reschedule.reset();
  }

  function confirm() {
    if (!slot) return;
    reschedule.mutate(
      { id: appointment.id, doctorId, startAt: slot.start_at },
      {
        onSuccess: (updated) => {
          toast.success(T.rescheduled(formatSlotLong(updated.start_at)));
          onClose();
        },
        onError: (err) => {
          if (toApiError(err).code === "SLOT_TAKEN") setSlot(null);
        },
      },
    );
  }

  return (
    <Dialog
      open
      onClose={onClose}
      title={T.rescheduleTitle}
      description={T.keepCode(appointment.code)}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {T.keepOld}
          </Button>
          <Button
            onClick={confirm}
            disabled={!slot}
            loading={reschedule.isPending}
            loadingText={T.rescheduling}
          >
            {T.confirmReschedule}
          </Button>
        </>
      }
    >
      <div className="grid grid-cols-2 gap-2 text-sm">
        <div className="flex flex-col rounded-[10px] border border-line px-3 py-2.5">
          <span className="text-muted">{T.current}</span>
          <span className="font-semibold tabular-nums">{formatSlot(appointment.start_at)}</span>
        </div>
        <div
          className={cn(
            "flex flex-col rounded-[10px] px-3 py-2.5",
            slot
              ? "border-[1.5px] border-primary bg-primary-soft"
              : "border border-dashed border-line-strong",
          )}
          aria-live="polite"
        >
          <span className="text-muted">{T.next}</span>
          <span className="font-semibold tabular-nums">
            {slot ? formatSlot(slot.start_at) : T.notPicked}
          </span>
        </div>
      </div>

      <label className="flex flex-col gap-1.5 text-sm font-semibold">
        {T.doctorLabel}
        <select
          value={doctorId}
          onChange={(event) => changeDoctor(Number(event.target.value))}
          className={cn(inputClass(), "font-normal")}
        >
          <option value={appointment.doctor.id}>{T.keepDoctor(appointment.doctor.name)}</option>
          {others.map((doctor) => (
            <option key={doctor.id} value={doctor.id}>
              {doctor.name}
            </option>
          ))}
        </select>
      </label>

      {availability.isPending ? (
        <span aria-hidden="true" className="h-40 animate-pulse rounded-[10px] bg-divider" />
      ) : availability.isError ? (
        <Alert tone="danger">{TEXT.availability.loadError}</Alert>
      ) : !day ? (
        <Alert tone="warning">{T.noSlotsRange}</Alert>
      ) : (
        <>
          <div className="flex flex-col gap-2">
            <span className="text-sm font-semibold">{T.dayLabel}</span>
            <div className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1">
              {days.map((d) => {
                const open = d.status === "OPEN";
                const pressed = d.date === day.date;
                return (
                  <button
                    key={d.date}
                    type="button"
                    disabled={!open}
                    aria-pressed={pressed}
                    onClick={() => {
                      setPickedDay(d.date);
                      setSlot(null);
                    }}
                    className={cn(
                      "h-11 shrink-0 rounded-control px-3 text-sm whitespace-nowrap tabular-nums",
                      pressed && "bg-primary font-semibold text-white",
                      !pressed && open && "border border-line-strong hover:border-primary",
                      !open && "border border-line bg-ground text-muted line-through",
                    )}
                  >
                    {formatDayShort(d.date)}
                  </button>
                );
              })}
            </div>
          </div>
          <div className="flex flex-col gap-2">
            <span className="text-sm font-semibold">{T.slotsLabel}</span>
            <SlotPicker
              slots={day.slots}
              selected={slot?.start_at ?? null}
              onSelect={(picked) => {
                setSlot(picked);
                reschedule.reset();
              }}
              dayLabel={formatDayLong(day.date)}
              disabled={(s) =>
                doctorId === appointment.doctor.id && s.start_at === appointment.start_at
              }
            />
          </div>
        </>
      )}

      {error ? (
        <Alert tone="danger">
          {error.code === "SLOT_TAKEN" ? T.slotTakenKeep : errorMessage(error)}
        </Alert>
      ) : null}
    </Dialog>
  );
}
