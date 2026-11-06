"use client";

// Bác sĩ của quản trị (AD-doctors, UC14): mọi tài khoản bác sĩ kể cả đã khóa, tìm theo tên, email,
// lọc chuyên khoa; bấm tên để sửa ở panel bên phải, "Ca làm" mở lịch làm việc của bác sĩ đó.
import Link from "next/link";
import { useState } from "react";

import type { DoctorAdmin } from "@/shared/api/types";
import { cn } from "@/shared/lib/cn";
import { unaccent } from "@/shared/lib/format";
import { TEXT } from "@/shared/texts";
import { Alert } from "@/shared/ui/alert";
import { Avatar } from "@/shared/ui/avatar";
import { Button } from "@/shared/ui/button";
import { inputClass } from "@/shared/ui/field";
import { PlusIcon, SearchIcon } from "@/shared/ui/icons";

import { DoctorForm } from "./doctor-form";
import { useAdminDoctors, useAdminServices, useAdminSpecialties } from "./queries";

const T = TEXT.admin;

type Editing = { doctor: DoctorAdmin | null } | null;

function matches(doctor: DoctorAdmin, q: string): boolean {
  const words = unaccent(q).split(/\s+/).filter(Boolean);
  const text = unaccent(`${doctor.name} ${doctor.email}`);
  return words.every((word) => text.includes(word));
}

export function AdminDoctorsPage() {
  const doctors = useAdminDoctors();
  const specialties = useAdminSpecialties();
  const services = useAdminServices();
  const [q, setQ] = useState("");
  const [specialtyId, setSpecialtyId] = useState(0);
  const [editing, setEditing] = useState<Editing>(null);

  const all = doctors.data ?? [];
  const shown = all.filter(
    (doctor) => (!specialtyId || doctor.specialty.id === specialtyId) && matches(doctor, q),
  );
  const loading = doctors.isPending || specialties.isPending || services.isPending;
  const failed = doctors.isError || specialties.isError || services.isError;
  const HEAD = "border-b border-line px-3.5 py-2.5 text-left font-medium";
  const CELL = "border-b border-divider px-3.5 py-3";
  const C = T.doctorColumns;

  return (
    <main className="mx-auto flex w-full max-w-[1280px] flex-col gap-4 px-4 py-6 md:px-7">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold md:text-[26px] md:leading-[34px]">
          {T.doctorsTitle}
          {doctors.data ? <span className="font-normal text-muted"> · {all.length}</span> : null}
        </h1>
        <Button size="sm" onClick={() => setEditing({ doctor: null })}>
          <PlusIcon size={16} />
          {T.addDoctor}
        </Button>
      </div>
      <div className="flex flex-wrap gap-2">
        <label className="flex h-10 min-w-[220px] flex-1 items-center gap-2 rounded-control border border-line-strong bg-surface px-3 focus-within:border-primary">
          <SearchIcon size={16} className="text-muted" />
          <input
            type="search"
            value={q}
            aria-label={T.searchDoctors}
            placeholder={T.searchDoctorsPlaceholder}
            onChange={(event) => setQ(event.target.value)}
            className="min-w-0 flex-1 bg-transparent text-sm outline-none"
          />
        </label>
        <select
          aria-label={T.specialty}
          value={specialtyId}
          onChange={(event) => setSpecialtyId(Number(event.target.value))}
          className={cn(inputClass(false, "sm"), "max-w-[240px] flex-none")}
        >
          <option value={0}>{T.allSpecialties}</option>
          {(specialties.data ?? []).map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}
            </option>
          ))}
        </select>
      </div>

      <div className="flex flex-col gap-5 lg:flex-row lg:items-start">
        <div className="min-w-0 flex-1">
          {loading ? (
            <span aria-hidden="true" className="block h-64 animate-pulse rounded-card bg-divider" />
          ) : failed ? (
            <Alert tone="danger">{T.loadError}</Alert>
          ) : (
            <div className="overflow-x-auto rounded-card border border-line bg-surface">
              <table className="w-full min-w-[560px] border-collapse text-sm">
                <thead>
                  <tr className="bg-[#f9fbfb] text-muted">
                    <th scope="col" className={HEAD}>
                      {C.doctor}
                    </th>
                    <th scope="col" className={HEAD}>
                      {C.specialty}
                    </th>
                    <th scope="col" className={HEAD}>
                      {C.services}
                    </th>
                    <th scope="col" className={HEAD}>
                      {C.account}
                    </th>
                    <th scope="col" className={HEAD}>
                      {C.schedule}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {shown.map((doctor) => (
                    <tr
                      key={doctor.id}
                      className={editing?.doctor?.id === doctor.id ? "bg-[#f4faf9]" : undefined}
                    >
                      <td className={CELL}>
                        <span className="flex items-center gap-2.5">
                          <Avatar id={doctor.id} name={doctor.name} size="xs" />
                          <span className="min-w-0">
                            <button
                              type="button"
                              onClick={() => setEditing({ doctor })}
                              className="text-left font-semibold hover:text-primary-ink hover:underline"
                            >
                              {doctor.name}
                            </button>
                            <span className="block truncate text-muted">{doctor.email}</span>
                          </span>
                        </span>
                      </td>
                      <td className={CELL}>{doctor.specialty.name}</td>
                      <td className={cn(CELL, "tabular-nums")}>{doctor.service_ids.length}</td>
                      <td
                        className={cn(
                          CELL,
                          "font-semibold",
                          doctor.is_active ? "text-success" : "text-danger",
                        )}
                      >
                        {doctor.is_active ? T.active : T.locked}
                      </td>
                      <td className={CELL}>
                        <Link
                          href={`/admin/schedules/${doctor.id}`}
                          className="font-medium text-primary hover:underline"
                        >
                          {T.shifts}
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
        {editing ? (
          <DoctorForm
            key={editing.doctor?.id ?? "new"}
            doctor={editing.doctor}
            specialties={specialties.data ?? []}
            services={services.data ?? []}
            onDone={() => setEditing(null)}
          />
        ) : null}
      </div>
    </main>
  );
}
