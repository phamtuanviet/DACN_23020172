// Chỉ dùng trong client component.
// Form thêm, sửa chuyên khoa và dịch vụ (AD-catalog, UC13, FR-CAT-01, 02, 05). Kiểm tra dữ liệu ở
// backend; lỗi từng ô hiện ngay dưới ô (details.fields). Danh mục không xóa cứng, chỉ ẩn.
import { useState, type ReactNode, type SyntheticEvent } from "react";

import { errorMessage, fieldErrors, toApiError } from "@/shared/api/errors";
import type { ServiceAdmin, SpecialtyAdmin } from "@/shared/api/types";
import { cn } from "@/shared/lib/cn";
import { TEXT } from "@/shared/texts";
import { Alert } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Field, inputClass } from "@/shared/ui/field";
import { CloseIcon } from "@/shared/ui/icons";
import { toast } from "@/shared/ui/toast";

import { useSaveService, useSaveSpecialty } from "./queries";

const T = TEXT.admin;
const DURATIONS = Array.from({ length: 23 }, (_, i) => 10 + i * 5); // 10–120 phút, bội số 5

export function SidePanel({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  return (
    <aside
      aria-label={title}
      className="order-first flex w-full shrink-0 flex-col gap-4 rounded-card border border-line bg-surface p-5 shadow-lg lg:sticky lg:top-6 lg:order-none lg:w-[380px]"
    >
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-[17px] leading-6 font-semibold">{title}</h2>
        <button
          type="button"
          aria-label={T.close}
          onClick={onClose}
          className="-m-2 rounded-control p-2 hover:bg-ground"
        >
          <CloseIcon size={18} />
        </button>
      </div>
      {children}
    </aside>
  );
}

export function VisibleToggle({
  checked,
  onChange,
  hint,
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
  hint: string;
}) {
  return (
    <label className="flex items-center justify-between gap-3 rounded-control border border-divider px-3 py-2.5">
      <span className="flex flex-col">
        <b className="text-sm">{T.visible}</b>
        <span className="text-[13px] leading-[18px] text-muted">{hint}</span>
      </span>
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="size-[22px] shrink-0 accent-primary"
      />
    </label>
  );
}

function FormActions({ saving, onCancel }: { saving: boolean; onCancel: () => void }) {
  return (
    <div className="flex justify-end gap-2">
      <Button variant="secondary" onClick={onCancel}>
        {T.cancel}
      </Button>
      <Button type="submit" loading={saving} loadingText={T.saving}>
        {T.save}
      </Button>
    </div>
  );
}

export function SpecialtyForm({
  specialty,
  onDone,
}: {
  specialty: SpecialtyAdmin | null;
  onDone: () => void;
}) {
  const [name, setName] = useState(specialty?.name ?? "");
  const [description, setDescription] = useState(specialty?.description ?? "");
  const [active, setActive] = useState(specialty?.is_active ?? true);
  const save = useSaveSpecialty();
  const error = save.error ? toApiError(save.error) : null;
  const fields = error ? fieldErrors(error) : {};

  function submit(event: SyntheticEvent<HTMLFormElement>) {
    event.preventDefault();
    save.mutate(
      {
        id: specialty?.id,
        body: {
          name,
          description: description || null,
          ...(specialty ? { is_active: active } : {}),
        },
      },
      {
        onSuccess: (saved) => {
          toast.success(T.saved(saved.name));
          onDone();
        },
      },
    );
  }

  return (
    <SidePanel title={specialty ? T.editSpecialty : T.newSpecialty} onClose={onDone}>
      <form onSubmit={submit} noValidate className="flex flex-col gap-3.5">
        <Field label={T.specialtyName} error={fields.name}>
          {({ inputId, describedBy, invalid }) => (
            <input
              id={inputId}
              value={name}
              maxLength={100}
              required
              aria-describedby={describedBy}
              aria-invalid={invalid || undefined}
              onChange={(event) => setName(event.target.value)}
              className={inputClass(invalid)}
            />
          )}
        </Field>
        <Field
          label={T.specialtyDescription}
          hint={T.specialtyDescriptionHint}
          error={fields.description}
        >
          {({ inputId, describedBy, invalid }) => (
            <textarea
              id={inputId}
              rows={3}
              value={description}
              maxLength={2000}
              aria-describedby={describedBy}
              aria-invalid={invalid || undefined}
              onChange={(event) => setDescription(event.target.value)}
              className={inputClass(invalid, "multiline")}
            />
          )}
        </Field>
        {specialty ? (
          <VisibleToggle checked={active} onChange={setActive} hint={T.specialtyVisibleHint} />
        ) : null}
        {error && Object.keys(fields).length === 0 ? (
          <Alert tone="danger">{errorMessage(error)}</Alert>
        ) : null}
        <FormActions saving={save.isPending} onCancel={onDone} />
      </form>
    </SidePanel>
  );
}

export function ServiceForm({
  service,
  specialties,
  onDone,
}: {
  service: ServiceAdmin | null;
  specialties: SpecialtyAdmin[];
  onDone: () => void;
}) {
  const [name, setName] = useState(service?.name ?? "");
  const [specialtyId, setSpecialtyId] = useState(service?.specialty.id ?? 0);
  const [scope, setScope] = useState(service?.scope_description ?? "");
  const [duration, setDuration] = useState(service?.duration_min ?? 20);
  const [price, setPrice] = useState(String(service?.ref_price_vnd ?? ""));
  const [active, setActive] = useState(service?.is_active ?? true);
  const save = useSaveService();
  const error = save.error ? toApiError(save.error) : null;
  const fields = error ? fieldErrors(error) : {};

  function submit(event: SyntheticEvent<HTMLFormElement>) {
    event.preventDefault();
    save.mutate(
      {
        id: service?.id,
        body: {
          name,
          specialty_id: specialtyId,
          scope_description: scope,
          duration_min: duration,
          ref_price_vnd: Number(price) || 0,
          ...(service ? { is_active: active } : {}),
        },
      },
      {
        onSuccess: (saved) => {
          toast.success(T.saved(saved.name));
          onDone();
        },
      },
    );
  }

  return (
    <SidePanel title={service ? T.editService : T.newService} onClose={onDone}>
      <form onSubmit={submit} noValidate className="flex flex-col gap-3.5">
        <Field label={T.serviceName} error={fields.name}>
          {({ inputId, describedBy, invalid }) => (
            <input
              id={inputId}
              value={name}
              maxLength={150}
              aria-describedby={describedBy}
              aria-invalid={invalid || undefined}
              onChange={(event) => setName(event.target.value)}
              className={inputClass(invalid)}
            />
          )}
        </Field>
        <Field label={T.specialty} error={fields.specialty_id}>
          {({ inputId, describedBy, invalid }) => (
            <select
              id={inputId}
              value={specialtyId || ""}
              aria-describedby={describedBy}
              aria-invalid={invalid || undefined}
              onChange={(event) => setSpecialtyId(Number(event.target.value))}
              className={inputClass(invalid)}
            >
              <option value="" disabled>
                {T.pickSpecialty}
              </option>
              {specialties.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                  {item.is_active ? "" : T.hiddenSuffix}
                </option>
              ))}
            </select>
          )}
        </Field>
        <Field label={T.scope} hint={T.scopeHint} error={fields.scope_description}>
          {({ inputId, describedBy, invalid }) => (
            <textarea
              id={inputId}
              rows={4}
              value={scope}
              maxLength={2000}
              aria-describedby={describedBy}
              aria-invalid={invalid || undefined}
              onChange={(event) => setScope(event.target.value)}
              className={inputClass(invalid, "multiline")}
            />
          )}
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label={T.duration} hint={T.durationHint} error={fields.duration_min}>
            {({ inputId, describedBy, invalid }) => (
              <select
                id={inputId}
                value={duration}
                aria-describedby={describedBy}
                aria-invalid={invalid || undefined}
                onChange={(event) => setDuration(Number(event.target.value))}
                className={inputClass(invalid)}
              >
                {DURATIONS.map((minutes) => (
                  <option key={minutes} value={minutes}>
                    {T.minutes(minutes)}
                  </option>
                ))}
              </select>
            )}
          </Field>
          <Field label={T.price} error={fields.ref_price_vnd}>
            {({ inputId, describedBy, invalid }) => (
              <input
                id={inputId}
                inputMode="numeric"
                value={price}
                aria-describedby={describedBy}
                aria-invalid={invalid || undefined}
                onChange={(event) => setPrice(event.target.value.replace(/\D/g, ""))}
                className={cn(inputClass(invalid), "tabular-nums")}
              />
            )}
          </Field>
        </div>
        {service ? (
          <VisibleToggle
            checked={active}
            onChange={setActive}
            hint={T.visibleHint(service.appointment_count)}
          />
        ) : null}
        {error && Object.keys(fields).length === 0 ? (
          <Alert tone="danger">{errorMessage(error)}</Alert>
        ) : null}
        <FormActions saving={save.isPending} onCancel={onDone} />
      </form>
    </SidePanel>
  );
}
