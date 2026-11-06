// Chỉ dùng trong client component.
// Form tạo, sửa tài khoản bác sĩ (AD-doctors, UC14, FR-ADM-01, FR-CAT-03): chức danh, họ tên,
// chuyên khoa, dịch vụ thực hiện, khóa tài khoản. Email cố định sau khi tạo; mật khẩu ban đầu do
// quản trị đặt và gửi riêng cho bác sĩ. Khóa không hủy lịch đã đặt, nên form nhắc số lịch sắp tới.
import Link from "next/link";
import { useState, type SyntheticEvent } from "react";

import { errorMessage, fieldErrors, toApiError } from "@/shared/api/errors";
import type { DoctorAdmin, Gender, ServiceAdmin, SpecialtyAdmin } from "@/shared/api/types";
import { cn } from "@/shared/lib/cn";
import { TEXT } from "@/shared/texts";
import { Alert } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Field, inputClass, PasswordInput } from "@/shared/ui/field";
import { toast } from "@/shared/ui/toast";

import { SidePanel } from "./catalog-forms";
import { useCreateDoctor, useUpdateDoctor } from "./queries";

const T = TEXT.admin;
const GENDERS: Gender[] = ["FEMALE", "MALE", "OTHER"];

export function DoctorForm({
  doctor,
  specialties,
  services,
  onDone,
}: {
  doctor: DoctorAdmin | null;
  specialties: SpecialtyAdmin[];
  services: ServiceAdmin[];
  onDone: () => void;
}) {
  const [title, setTitle] = useState(doctor?.title ?? "BS.");
  const [fullName, setFullName] = useState(doctor?.full_name ?? "");
  const [email, setEmail] = useState(doctor?.email ?? "");
  const [password, setPassword] = useState("");
  const [gender, setGender] = useState<Gender>(doctor?.gender ?? "FEMALE");
  const [specialtyId, setSpecialtyId] = useState(doctor?.specialty.id ?? 0);
  const [serviceIds, setServiceIds] = useState<number[]>(doctor?.service_ids ?? []);
  const [bio, setBio] = useState(doctor?.bio ?? "");
  const [locked, setLocked] = useState(doctor ? !doctor.is_active : false);
  const create = useCreateDoctor();
  const update = useUpdateDoctor();
  const mutation = doctor ? update : create;
  const error = mutation.error ? toApiError(mutation.error) : null;
  const fields = error ? fieldErrors(error) : {};
  if (error?.code === "EMAIL_TAKEN") fields.email = errorMessage(error);

  const options = services.filter((service) => service.specialty.id === specialtyId);
  const chosen = serviceIds.filter((id) => options.some((service) => service.id === id));
  const lockingWithBookings = doctor !== null && locked && doctor.upcoming_count > 0;

  function changeSpecialty(id: number) {
    setSpecialtyId(id);
    setServiceIds([]);
  }

  function toggleService(id: number, checked: boolean) {
    setServiceIds((current) => (checked ? [...current, id] : current.filter((x) => x !== id)));
  }

  function submit(event: SyntheticEvent<HTMLFormElement>) {
    event.preventDefault();
    const profile = {
      title,
      full_name: fullName,
      gender,
      specialty_id: specialtyId,
      bio: bio || null,
      service_ids: chosen,
    };
    const onSuccess = (saved: DoctorAdmin) => {
      toast.success(doctor ? T.saved(saved.name) : T.doctorCreated(saved.name));
      onDone();
    };
    if (doctor) {
      update.mutate({ id: doctor.id, body: { ...profile, is_active: !locked } }, { onSuccess });
    } else {
      create.mutate({ ...profile, email, password }, { onSuccess });
    }
  }

  return (
    <SidePanel title={doctor ? doctor.name : T.newDoctor} onClose={onDone}>
      <form onSubmit={submit} noValidate className="flex flex-col gap-3.5">
        <div className="grid grid-cols-[110px_minmax(0,1fr)] gap-3">
          <Field label={T.title} error={fields.title}>
            {({ inputId, describedBy, invalid }) => (
              <input
                id={inputId}
                value={title}
                maxLength={50}
                aria-describedby={describedBy}
                aria-invalid={invalid || undefined}
                onChange={(event) => setTitle(event.target.value)}
                className={inputClass(invalid)}
              />
            )}
          </Field>
          <Field label={T.fullName} error={fields.full_name}>
            {({ inputId, describedBy, invalid }) => (
              <input
                id={inputId}
                value={fullName}
                maxLength={100}
                autoComplete="off"
                aria-describedby={describedBy}
                aria-invalid={invalid || undefined}
                onChange={(event) => setFullName(event.target.value)}
                className={inputClass(invalid)}
              />
            )}
          </Field>
        </div>
        <Field
          label={T.loginEmail}
          hint={doctor ? T.emailFixed : undefined}
          error={doctor ? undefined : fields.email}
        >
          {({ inputId, describedBy, invalid }) => (
            <input
              id={inputId}
              type="email"
              value={email}
              maxLength={255}
              autoComplete="off"
              readOnly={doctor !== null}
              aria-describedby={describedBy}
              aria-invalid={invalid || undefined}
              onChange={(event) => setEmail(event.target.value)}
              className={cn(inputClass(invalid), "read-only:bg-ground read-only:text-muted")}
            />
          )}
        </Field>
        {doctor ? null : (
          <Field label={T.initialPassword} hint={T.passwordHint} error={fields.password}>
            {({ inputId, describedBy, invalid }) => (
              <PasswordInput
                id={inputId}
                value={password}
                autoComplete="new-password"
                maxLength={128}
                invalid={invalid}
                aria-describedby={describedBy}
                onChange={(event) => setPassword(event.target.value)}
              />
            )}
          </Field>
        )}
        <div className="grid grid-cols-2 gap-3">
          <Field label={T.gender} error={fields.gender}>
            {({ inputId, describedBy, invalid }) => (
              <select
                id={inputId}
                value={gender}
                aria-describedby={describedBy}
                aria-invalid={invalid || undefined}
                onChange={(event) => setGender(event.target.value as Gender)}
                className={inputClass(invalid)}
              >
                {GENDERS.map((value) => (
                  <option key={value} value={value}>
                    {T.genders[value]}
                  </option>
                ))}
              </select>
            )}
          </Field>
          <Field label={T.specialty} error={fields.specialty_id}>
            {({ inputId, describedBy, invalid }) => (
              <select
                id={inputId}
                value={specialtyId || ""}
                aria-describedby={describedBy}
                aria-invalid={invalid || undefined}
                onChange={(event) => changeSpecialty(Number(event.target.value))}
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
        </div>
        <fieldset className="flex flex-col gap-1.5">
          <legend className="mb-1.5 text-sm font-semibold">{T.services}</legend>
          {specialtyId === 0 ? (
            <p className="text-sm text-muted">{T.servicesHint}</p>
          ) : options.length === 0 ? (
            <p className="text-sm text-muted">{T.noServices}</p>
          ) : (
            options.map((service) => (
              <label key={service.id} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={chosen.includes(service.id)}
                  onChange={(event) => toggleService(service.id, event.target.checked)}
                  className="size-[18px] accent-primary"
                />
                <span className={service.is_active ? undefined : "text-muted"}>
                  {service.name}
                  {service.is_active ? "" : T.hiddenSuffix}
                </span>
              </label>
            ))
          )}
          {fields.service_ids ? (
            <span className="text-[13px] text-danger">{fields.service_ids}</span>
          ) : null}
        </fieldset>
        <Field label={T.bio} error={fields.bio}>
          {({ inputId, describedBy, invalid }) => (
            <textarea
              id={inputId}
              rows={3}
              value={bio}
              maxLength={2000}
              aria-describedby={describedBy}
              aria-invalid={invalid || undefined}
              onChange={(event) => setBio(event.target.value)}
              className={inputClass(invalid, "multiline")}
            />
          )}
        </Field>
        {doctor ? (
          <label className="flex items-center justify-between gap-3 rounded-control border border-danger-line bg-[#fef8f7] px-3 py-2.5">
            <span className="flex flex-col">
              <b className="text-sm text-danger-ink">{T.lockAccount}</b>
              <span className="text-[13px] leading-[18px] text-[#5c2a25]">{T.lockHint}</span>
            </span>
            <input
              type="checkbox"
              checked={locked}
              onChange={(event) => setLocked(event.target.checked)}
              className="size-[22px] shrink-0 accent-danger"
            />
          </label>
        ) : null}
        {lockingWithBookings ? (
          <Alert tone="warning">
            {T.lockWarning(doctor.upcoming_count)}{" "}
            <Link
              href={`/admin/appointments?doctor=${doctor.id}&status=BOOKED`}
              className="font-semibold underline"
            >
              {T.viewUpcoming}
            </Link>
          </Alert>
        ) : null}
        {error && Object.keys(fields).length === 0 ? (
          <Alert tone="danger">{errorMessage(error)}</Alert>
        ) : null}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onDone}>
            {T.cancel}
          </Button>
          <Button type="submit" loading={mutation.isPending} loadingText={T.saving}>
            {T.save}
          </Button>
        </div>
      </form>
    </SidePanel>
  );
}
