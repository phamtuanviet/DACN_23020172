// Chỉ dùng trong client component.
// Form ca làm và ngày nghỉ (AD-schedule, UC15). Thêm ca không ảnh hưởng lịch đã đặt nên lưu ngay;
// sửa, xóa ca và thêm ngày nghỉ đi hai bước như UC15 bước 4–6: xem trước (`dry_run`) danh sách lịch
// bị ảnh hưởng, rồi mới lưu và gắn cờ các lịch đó (BR-10). Hệ thống không tự hủy lịch.
import { useState, type ReactNode } from "react";

import { errorMessage, fieldErrors, toApiError, type ApiError } from "@/shared/api/errors";
import type { AffectedAppointment, Shift } from "@/shared/api/types";
import {
  clinicDateTime,
  clinicDay,
  formatDayShort,
  formatTime,
  weekdayName,
} from "@/shared/lib/datetime";
import { TEXT } from "@/shared/texts";
import { Alert } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Field, inputClass } from "@/shared/ui/field";
import { toast } from "@/shared/ui/toast";

import { SidePanel } from "./catalog-forms";
import { useCreateTimeOff, useShiftChange, type ShiftInput } from "./queries";
import { hhmm } from "./schedule-plan";

const T = TEXT.admin;
const WEEKDAYS = [1, 2, 3, 4, 5, 6, 7];

function ErrorBox({ error, fields }: { error: ApiError | null; fields: Record<string, string> }) {
  if (!error || Object.keys(fields).length > 0) return null;
  return <Alert tone="danger">{errorMessage(error)}</Alert>;
}

export function AffectedList({ items }: { items: AffectedAppointment[] }) {
  return (
    <div
      role="status"
      className="flex flex-col gap-1.5 rounded-[10px] border border-amber-line bg-amber-soft p-3 text-sm text-amber-ink"
    >
      <b>{T.affectedTitle(items.length)}</b>
      {items.length > 0 ? (
        <ul className="flex flex-col gap-0.5">
          {items.map((item) => (
            <li key={item.id} className="tabular-nums">
              {formatDayShort(clinicDay(item.start_at))} {formatTime(item.start_at)} ·{" "}
              {item.patient_name} · {item.service_name}
            </li>
          ))}
        </ul>
      ) : null}
      <span>{T.affectedNote(items.length)}</span>
    </div>
  );
}

function Grid2({ children }: { children: ReactNode }) {
  return <div className="grid grid-cols-2 gap-3">{children}</div>;
}

/** Thêm ca (`shift` rỗng) hoặc sửa, xóa ca có sẵn. */
export function ShiftForm({
  doctorId,
  shift,
  defaultWeekday,
  defaultFrom,
  onDone,
}: {
  doctorId: number;
  shift: Shift | null;
  defaultWeekday: number;
  defaultFrom: string;
  onDone: () => void;
}) {
  const [values, setValues] = useState<ShiftInput>({
    weekday: shift?.weekday ?? defaultWeekday,
    start_time: hhmm(shift?.start_time ?? "07:00"),
    end_time: hhmm(shift?.end_time ?? "11:30"),
    valid_from: shift?.valid_from ?? defaultFrom,
    valid_to: shift?.valid_to ?? null,
  });
  // Kết quả xem trước của đúng thao tác sắp lưu; đổi dữ liệu thì phải xem lại.
  const [preview, setPreview] = useState<{
    kind: "update" | "delete";
    affected: AffectedAppointment[];
  } | null>(null);
  const change = useShiftChange();
  const error = change.error ? toApiError(change.error) : null;
  const fields = error ? fieldErrors(error) : {};

  function set<K extends keyof ShiftInput>(key: K, value: ShiftInput[K]) {
    setValues((current) => ({ ...current, [key]: value }));
    setPreview(null);
    change.reset();
  }

  function run(kind: "create" | "update" | "delete", dryRun: boolean) {
    const onSuccess = (result: { dry_run: boolean; affected: AffectedAppointment[] }) => {
      if (result.dry_run && kind !== "create") {
        setPreview({ kind, affected: result.affected });
        return;
      }
      toast.success(kind === "delete" ? T.shiftDeleted : T.shiftSaved);
      onDone();
    };
    if (kind === "create") change.mutate({ kind, doctorId, body: values }, { onSuccess });
    else if (kind === "update" && shift)
      change.mutate({ kind, doctorId, shiftId: shift.id, body: values, dryRun }, { onSuccess });
    else if (kind === "delete" && shift)
      change.mutate({ kind, doctorId, shiftId: shift.id, dryRun }, { onSuccess });
  }

  const time = (key: "start_time" | "end_time", label: string) => (
    <Field label={label} error={fields[key]}>
      {({ inputId, describedBy, invalid }) => (
        <input
          id={inputId}
          type="time"
          step={300}
          value={values[key]}
          aria-describedby={describedBy}
          aria-invalid={invalid || undefined}
          onChange={(event) => set(key, event.target.value)}
          className={inputClass(invalid)}
        />
      )}
    </Field>
  );

  return (
    <SidePanel title={shift ? T.editShift : T.addShift} onClose={onDone}>
      <div className="flex flex-col gap-3.5">
        <Field label={T.weekday} error={fields.weekday}>
          {({ inputId, describedBy, invalid }) => (
            <select
              id={inputId}
              value={values.weekday}
              aria-describedby={describedBy}
              aria-invalid={invalid || undefined}
              onChange={(event) => set("weekday", Number(event.target.value))}
              className={inputClass(invalid)}
            >
              {WEEKDAYS.map((day) => (
                <option key={day} value={day}>
                  {weekdayName(day)}
                </option>
              ))}
            </select>
          )}
        </Field>
        <Grid2>
          {time("start_time", T.startTime)}
          {time("end_time", T.endTime)}
        </Grid2>
        <Grid2>
          <Field label={T.validFrom} error={fields.valid_from}>
            {({ inputId, describedBy, invalid }) => (
              <input
                id={inputId}
                type="date"
                value={values.valid_from}
                aria-describedby={describedBy}
                aria-invalid={invalid || undefined}
                onChange={(event) => set("valid_from", event.target.value)}
                className={inputClass(invalid)}
              />
            )}
          </Field>
          <Field label={T.validTo} hint={T.validToHint} error={fields.valid_to}>
            {({ inputId, describedBy, invalid }) => (
              <input
                id={inputId}
                type="date"
                value={values.valid_to ?? ""}
                min={values.valid_from}
                aria-describedby={describedBy}
                aria-invalid={invalid || undefined}
                onChange={(event) => set("valid_to", event.target.value || null)}
                className={inputClass(invalid)}
              />
            )}
          </Field>
        </Grid2>
        {preview ? <AffectedList items={preview.affected} /> : null}
        <ErrorBox error={error} fields={fields} />
        <div className="flex flex-wrap justify-end gap-2">
          {shift && preview?.kind !== "update" ? (
            <Button
              variant="danger"
              loading={change.isPending && change.variables?.kind === "delete"}
              loadingText={T.previewing}
              onClick={() => run("delete", preview?.kind !== "delete")}
            >
              {preview?.kind === "delete"
                ? T.deleteAndFlag(preview.affected.length)
                : T.deleteShift}
            </Button>
          ) : null}
          <Button variant="secondary" onClick={onDone}>
            {T.cancel}
          </Button>
          {preview?.kind !== "delete" ? (
            <Button
              loading={change.isPending && change.variables?.kind !== "delete"}
              loadingText={T.saving}
              onClick={() =>
                shift ? run("update", preview?.kind !== "update") : run("create", false)
              }
            >
              {!shift
                ? T.save
                : preview?.kind === "update"
                  ? T.saveAndFlag(preview.affected.length)
                  : T.preview}
            </Button>
          ) : null}
        </div>
      </div>
    </SidePanel>
  );
}

export function TimeOffForm({
  doctorId,
  defaultDay,
  onDone,
}: {
  doctorId: number;
  defaultDay: string;
  onDone: () => void;
}) {
  const [from, setFrom] = useState({ day: defaultDay, time: "00:00" });
  const [to, setTo] = useState({ day: defaultDay, time: "23:59" });
  const [reason, setReason] = useState("");
  const [affected, setAffected] = useState<AffectedAppointment[] | null>(null);
  const create = useCreateTimeOff();
  const error = create.error ? toApiError(create.error) : null;
  const fields = error ? fieldErrors(error) : {};

  function edited() {
    setAffected(null);
    create.reset();
  }

  function submit() {
    const body = {
      start_at: clinicDateTime(from.day, from.time),
      end_at: clinicDateTime(to.day, to.time),
      reason: reason.trim() || null,
    };
    create.mutate(
      { doctorId, body, dryRun: affected === null },
      {
        onSuccess: (result) => {
          if (result.dry_run) {
            setAffected(result.affected);
            return;
          }
          toast.success(T.timeOffSaved(result.affected.length));
          onDone();
        },
      },
    );
  }

  const moment = (
    label: string,
    value: { day: string; time: string },
    onChange: (value: { day: string; time: string }) => void,
    error?: string,
  ) => (
    <fieldset className="flex flex-col gap-1.5">
      <legend className="mb-1.5 text-sm font-semibold">{label}</legend>
      <div className="grid grid-cols-[minmax(0,1fr)_140px] gap-2">
        <input
          type="date"
          aria-label={`${label}, ${T.dayWord}`}
          value={value.day}
          onChange={(event) => {
            onChange({ ...value, day: event.target.value });
            edited();
          }}
          className={inputClass(Boolean(error))}
        />
        <input
          type="time"
          aria-label={`${label}, ${T.timeWord}`}
          value={value.time}
          onChange={(event) => {
            onChange({ ...value, time: event.target.value });
            edited();
          }}
          className={inputClass(Boolean(error))}
        />
      </div>
      {error ? <span className="text-[13px] text-danger">{error}</span> : null}
    </fieldset>
  );

  return (
    <SidePanel title={T.addTimeOff} onClose={onDone}>
      <div className="flex flex-col gap-3.5">
        {moment(T.from, from, setFrom, fields.start_at)}
        {moment(T.to, to, setTo, fields.end_at)}
        <Field label={T.reason} error={fields.reason}>
          {({ inputId, describedBy, invalid }) => (
            <input
              id={inputId}
              value={reason}
              maxLength={255}
              placeholder={T.reasonPlaceholder}
              aria-describedby={describedBy}
              aria-invalid={invalid || undefined}
              onChange={(event) => {
                setReason(event.target.value);
                edited();
              }}
              className={inputClass(invalid)}
            />
          )}
        </Field>
        {affected ? <AffectedList items={affected} /> : null}
        <ErrorBox error={error} fields={fields} />
        <div className="flex flex-wrap items-center justify-end gap-2">
          <Button variant="secondary" onClick={onDone}>
            {T.cancel}
          </Button>
          <Button
            onClick={submit}
            loading={create.isPending}
            loadingText={affected ? T.saving : T.previewing}
          >
            {affected ? T.saveAndFlag(affected.length) : T.preview}
          </Button>
        </div>
      </div>
    </SidePanel>
  );
}
