// Chỉ dùng trong client component. Hộp thoại hủy lịch (P-dialogs, UC07): lý do không bắt buộc,
// nói rõ hủy rồi không khôi phục được. Lý do hủy là dữ liệu cá nhân, chỉ gửi lên backend.
import { useId, useState } from "react";

import { errorMessage, toApiError } from "@/shared/api/errors";
import type { Appointment } from "@/shared/api/types";
import { useCancelAppointment } from "@/shared/appointments/queries";
import { cn } from "@/shared/lib/cn";
import { clinicDay, formatDayLong, formatTime } from "@/shared/lib/datetime";
import { TEXT } from "@/shared/texts";
import { Alert } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Dialog } from "@/shared/ui/dialog";
import { inputClass } from "@/shared/ui/field";
import { toast } from "@/shared/ui/toast";

const T = TEXT.appointments;
const OTHER = T.otherReason;

export function CancelDialog({
  appointment,
  onClose,
  onCancelled,
}: {
  appointment: Appointment;
  onClose: () => void;
  onCancelled: (appointment: Appointment) => void;
}) {
  const otherId = useId();
  const [choice, setChoice] = useState("");
  const [other, setOther] = useState("");
  const cancel = useCancelAppointment();
  const error = cancel.error ? toApiError(cancel.error) : null;

  function confirm() {
    const reason = choice === OTHER ? other : choice;
    cancel.mutate(
      { id: appointment.id, reason },
      {
        onSuccess: (updated) => {
          toast.success(T.cancelled(updated.code));
          onCancelled(updated);
        },
      },
    );
  }

  const summary = [
    appointment.service.name,
    formatDayLong(clinicDay(appointment.start_at)),
    formatTime(appointment.start_at),
    appointment.doctor.name,
  ].join(" · ");

  return (
    <Dialog
      open
      onClose={onClose}
      title={T.cancelTitle}
      description={summary}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {T.keepAppointment}
          </Button>
          <Button
            variant="danger"
            onClick={confirm}
            loading={cancel.isPending}
            loadingText={T.cancelling}
          >
            {T.confirmCancel}
          </Button>
        </>
      }
    >
      <label className="flex flex-col gap-1.5 text-sm font-semibold">
        <span>
          {T.cancelReason} <span className="font-normal text-muted">{TEXT.booking.optional}</span>
        </span>
        <select
          value={choice}
          onChange={(event) => setChoice(event.target.value)}
          className={cn(inputClass(), "font-normal")}
        >
          <option value="">{T.noReasonOption}</option>
          {T.cancelReasons.map((reason) => (
            <option key={reason} value={reason}>
              {reason}
            </option>
          ))}
        </select>
      </label>
      {choice === OTHER ? (
        <div className="flex flex-col gap-1.5">
          <label htmlFor={otherId} className="sr-only">
            {T.otherReason}
          </label>
          <input
            id={otherId}
            value={other}
            maxLength={500}
            placeholder={T.otherReasonPlaceholder}
            onChange={(event) => setOther(event.target.value)}
            className={inputClass()}
          />
        </div>
      ) : null}
      <Alert tone="warning">{T.cancelWarning}</Alert>
      {error ? <Alert tone="danger">{errorMessage(error)}</Alert> : null}
    </Dialog>
  );
}
