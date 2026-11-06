// Chỉ dùng trong client component.
// Thao tác của quản trị trên một lịch hẹn (AD-appts, menu ⋯): đổi lịch, đổi trạng thái, gắn hoặc
// gỡ cờ cần xử lý, hủy lịch (FR-ADM-03, 04). Đổi và hủy dùng chung hộp thoại với bệnh nhân; backend
// nhận ra vai trò quản trị để bỏ mốc 2 giờ và ghi kênh ADMIN.
import { useEffect, useId, useRef, useState } from "react";

import { errorMessage, toApiError } from "@/shared/api/errors";
import type { AdminAppointment, AppointmentStatus } from "@/shared/api/types";
import { CancelDialog } from "@/shared/appointments/cancel-dialog";
import { RescheduleDialog } from "@/shared/appointments/reschedule-dialog";
import { cn } from "@/shared/lib/cn";
import { formatSlot } from "@/shared/lib/datetime";
import { TEXT } from "@/shared/texts";
import { Alert } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Dialog } from "@/shared/ui/dialog";
import { MoreIcon } from "@/shared/ui/icons";
import { toast } from "@/shared/ui/toast";

import { useChangeStatus, useSetAttention } from "./queries";

const T = TEXT.admin;
const STATUS = TEXT.appointments.statuses;

type Target = "ARRIVED" | "COMPLETED" | "NO_SHOW";
// Sơ đồ trạng thái (docs mục 5.5); hủy đi qua hộp thoại hủy để có lý do và email.
const NEXT: Partial<Record<AppointmentStatus, Target[]>> = {
  BOOKED: ["ARRIVED", "NO_SHOW"],
  ARRIVED: ["COMPLETED"],
};

export type AdminDialog = {
  kind: "reschedule" | "cancel" | "status";
  appointment: AdminAppointment;
} | null;

/** Các mục của menu ⋯ theo trạng thái lịch; rỗng thì không hiện nút. */
export function actionsOf(appointment: AdminAppointment) {
  const booked = appointment.status === "BOOKED";
  return {
    reschedule: booked,
    cancel: booked,
    status: (NEXT[appointment.status]?.length ?? 0) > 0,
    unflag: appointment.needs_attention,
    flag: booked && !appointment.needs_attention,
  };
}

export function AppointmentMenu({
  appointment,
  onOpen,
}: {
  appointment: AdminAppointment;
  onOpen: (dialog: NonNullable<AdminDialog>) => void;
}) {
  const [open, setOpen] = useState(false);
  const menuId = useId();
  const ref = useRef<HTMLDivElement>(null);
  const attention = useSetAttention();
  const actions = actionsOf(appointment);

  useEffect(() => {
    if (!open) return;
    function onPointer(event: PointerEvent) {
      if (!ref.current?.contains(event.target as Node)) setOpen(false);
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (!Object.values(actions).some(Boolean)) return null;

  function pick(kind: NonNullable<AdminDialog>["kind"]) {
    setOpen(false);
    onOpen({ kind, appointment });
  }

  function toggleFlag(value: boolean) {
    setOpen(false);
    attention.mutate(
      { id: appointment.id, value },
      {
        onSuccess: () =>
          toast.success(value ? T.flagged(appointment.code) : T.unflagged(appointment.code)),
        onError: (error) => toast.error(errorMessage(toApiError(error))),
      },
    );
  }

  const item =
    "flex h-10 w-full items-center rounded-[6px] px-2.5 text-left text-sm hover:bg-ground focus-visible:bg-ground";

  return (
    <div ref={ref} className="relative inline-block">
      <button
        type="button"
        aria-label={T.actionsFor(appointment.code)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        disabled={attention.isPending}
        onClick={() => setOpen((value) => !value)}
        className={cn(
          "flex size-9 items-center justify-center rounded-control",
          open
            ? "border-[1.5px] border-primary bg-primary-soft"
            : "border border-line bg-surface hover:border-primary",
        )}
      >
        <MoreIcon size={18} />
      </button>
      {open ? (
        <div
          id={menuId}
          role="menu"
          className="absolute top-11 right-0 z-20 flex w-52 flex-col rounded-[10px] border border-line bg-surface p-1.5 shadow-lg"
        >
          {actions.reschedule ? (
            <button
              type="button"
              role="menuitem"
              className={item}
              onClick={() => pick("reschedule")}
            >
              {T.reschedule}
            </button>
          ) : null}
          {actions.status ? (
            <button type="button" role="menuitem" className={item} onClick={() => pick("status")}>
              {T.changeStatus}
            </button>
          ) : null}
          {actions.unflag ? (
            <button
              type="button"
              role="menuitem"
              className={item}
              onClick={() => toggleFlag(false)}
            >
              {T.unflag}
            </button>
          ) : null}
          {actions.flag ? (
            <button type="button" role="menuitem" className={item} onClick={() => toggleFlag(true)}>
              {T.flag}
            </button>
          ) : null}
          {actions.cancel ? (
            <button
              type="button"
              role="menuitem"
              className={cn(item, "text-danger")}
              onClick={() => pick("cancel")}
            >
              {T.cancelAppointment}
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

/** Hộp thoại đang mở của trang lịch hẹn hoặc hàng chờ. */
export function AdminDialogs({ dialog, onClose }: { dialog: AdminDialog; onClose: () => void }) {
  if (!dialog) return null;
  if (dialog.kind === "reschedule")
    return <RescheduleDialog appointment={dialog.appointment} onClose={onClose} />;
  if (dialog.kind === "cancel")
    return (
      <CancelDialog
        appointment={dialog.appointment}
        reasons={T.cancelReasons}
        onClose={onClose}
        onCancelled={onClose}
      />
    );
  return <StatusDialog appointment={dialog.appointment} onClose={onClose} />;
}

function StatusDialog({
  appointment,
  onClose,
}: {
  appointment: AdminAppointment;
  onClose: () => void;
}) {
  const options = NEXT[appointment.status] ?? [];
  const [target, setTarget] = useState<Target | undefined>(options[0]);
  const change = useChangeStatus();
  const error = change.error ? toApiError(change.error) : null;
  const name = useId();

  function save() {
    if (!target) return;
    change.mutate(
      { id: appointment.id, status: target },
      {
        onSuccess: () => {
          toast.success(T.statusSaved(appointment.code, STATUS[target]));
          onClose();
        },
      },
    );
  }

  return (
    <Dialog
      open
      onClose={onClose}
      title={T.statusTitle}
      description={T.statusLead(appointment.code, formatSlot(appointment.start_at))}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {T.cancel}
          </Button>
          <Button
            onClick={save}
            disabled={!target}
            loading={change.isPending}
            loadingText={T.saving}
          >
            {T.statusSave}
          </Button>
        </>
      }
    >
      {options.length === 0 ? (
        <Alert tone="info">{T.noTransition}</Alert>
      ) : (
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-1 text-sm font-semibold">
            {T.statusTo} ({STATUS[appointment.status]} →)
          </legend>
          {options.map((option) => (
            <label
              key={option}
              className={cn(
                "flex h-12 items-center gap-3 rounded-control px-3",
                target === option
                  ? "border-[1.5px] border-primary bg-primary-soft"
                  : "border border-line",
              )}
            >
              <input
                type="radio"
                name={name}
                value={option}
                checked={target === option}
                onChange={() => {
                  setTarget(option);
                  change.reset();
                }}
                className="size-4 accent-primary"
              />
              {STATUS[option]}
            </label>
          ))}
        </fieldset>
      )}
      <p className="text-sm text-muted">{T.statusHint}</p>
      {error ? <Alert tone="danger">{errorMessage(error)}</Alert> : null}
    </Dialog>
  );
}
