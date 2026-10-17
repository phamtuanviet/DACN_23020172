// Hồ sơ bác sĩ (G-doctor, UC03): hồ sơ, lịch làm việc render phía server; chọn dịch vụ và giờ trống
// 7 ngày tới là client component (DoctorBooking).
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import type { DoctorDetail } from "@/shared/api/types";
import { TEXT } from "@/shared/texts";
import { Avatar } from "@/shared/ui/avatar";

import { getDoctor, searchDoctors } from "./api";
import { DoctorBooking } from "./doctor-booking";
import { DoctorCard, earliestServiceOf } from "./doctor-card";
import { summarizeWorkingHours } from "./schedule-text";

export async function loadDoctor(id: number): Promise<DoctorDetail> {
  const doctor = Number.isInteger(id) && id > 0 ? await getDoctor(id) : null;
  if (!doctor) notFound();
  return doctor;
}

export async function DoctorPage({ id, serviceId }: { id: number; serviceId?: number }) {
  const doctor = await loadDoctor(id);
  const colleagues = (await searchDoctors({ specialtyId: doctor.specialty.id }))
    .filter((d) => d.id !== doctor.id)
    .slice(0, 2);
  const selected = doctor.services.some((s) => s.id === serviceId)
    ? serviceId
    : doctor.services[0]?.id;
  const colleagueServiceIds = colleagues
    .map((d) => earliestServiceOf(d, selected))
    .filter((sid): sid is number => sid !== undefined);

  return (
    <main className="mx-auto flex w-full max-w-[1200px] flex-col gap-5 px-4 pt-5 pb-24 md:px-6">
      <nav aria-label={TEXT.doctor.breadcrumb} className="text-sm text-muted">
        <Link href="/" className="text-primary hover:text-primary-hover">
          {TEXT.nav.home}
        </Link>{" "}
        /{" "}
        <Link href="/services?tab=doctors" className="text-primary hover:text-primary-hover">
          {TEXT.nav.doctors}
        </Link>{" "}
        /{" "}
        <span aria-current="page" className="text-ink">
          {doctor.name}
        </span>
      </nav>

      <Suspense fallback={<ProfileCard doctor={doctor} />}>
        <DoctorBooking doctor={doctor} profile={<ProfileCard doctor={doctor} />} />
      </Suspense>

      {colleagues.length > 0 ? (
        <section aria-labelledby="bs-khac" className="flex flex-col gap-3">
          <h2 id="bs-khac" className="mt-2 text-lg leading-[26px] font-semibold">
            {TEXT.doctor.others}
          </h2>
          <ul className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {colleagues.map((colleague) => (
              <li key={colleague.id}>
                <DoctorCard
                  doctor={colleague}
                  serviceIds={colleagueServiceIds}
                  preferredServiceId={selected}
                  layout="row"
                  className="h-full"
                />
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </main>
  );
}

function ProfileCard({ doctor }: { doctor: DoctorDetail }) {
  const schedule = summarizeWorkingHours(doctor.working_hours);
  return (
    <div className="flex flex-col gap-3.5 rounded-card border border-line bg-surface p-6">
      <div className="flex items-center gap-4">
        <Avatar id={doctor.id} name={doctor.name} size="xl" />
        <div className="flex flex-col gap-0.5">
          <h1 className="text-[26px] leading-[34px] font-bold">{doctor.name}</h1>
          <span className="text-muted">
            {doctor.specialty.name} · {TEXT.doctor.genders[doctor.gender]}
          </span>
        </div>
      </div>
      {doctor.bio ? <p className="text-subtle">{doctor.bio}</p> : null}
      <dl className="grid grid-cols-[110px_minmax(0,1fr)] gap-x-3 gap-y-2 border-t border-divider pt-3.5 text-[15px] leading-[22px]">
        <dt className="text-muted">{TEXT.doctor.schedule}</dt>
        <dd className="flex flex-col gap-1">
          {schedule.length > 0
            ? schedule.map((line) => (
                <span key={line.days}>
                  {line.days}
                  <br />
                  {line.hours}
                </span>
              ))
            : TEXT.doctor.noSchedule}
        </dd>
      </dl>
    </div>
  );
}
