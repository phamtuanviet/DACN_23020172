// Trang chủ (G-home, G-home-m): render phía server từ danh mục cache 5 phút; riêng "Giờ trống gần
// nhất" và "Sớm nhất" của bác sĩ là client component, luôn lấy mới (docs mục 9.1).
import Image from "next/image";
import Link from "next/link";

import type { Doctor, Service, Specialty } from "@/shared/api/types";
import { formatPrice } from "@/shared/lib/format";
import { CLINIC, TEXT } from "@/shared/texts";
import { buttonClass } from "@/shared/ui/button";
import { ChatIcon, CheckIcon, ChevronDownIcon } from "@/shared/ui/icons";

import { getSpecialties, searchDoctors, searchServices } from "./api";
import { DoctorCard, earliestServiceOf } from "./doctor-card";
import { NearestSlotCard } from "./nearest-slot-card";
import { openStatus } from "./schedule-text";
import { SearchForm } from "./search-form";
import { specialtyMedia } from "@/shared/lib/specialty-media";

const WRAP = "mx-auto w-full max-w-[1200px] px-4 md:px-6";
const H2 = "text-2xl leading-8 font-bold tracking-[-0.01em] md:text-[30px] md:leading-[38px]";

/** Mỗi chuyên khoa một bác sĩ cho đa dạng, tối đa 4 người (mục "Bác sĩ của phòng khám"). */
function featuredDoctors(doctors: Doctor[], specialties: Specialty[]): Doctor[] {
  const picked = specialties
    .map((specialty) => doctors.find((d) => d.specialty.id === specialty.id))
    .filter((d): d is Doctor => d !== undefined);
  return picked.slice(0, 4);
}

export async function HomePage() {
  const [specialties, services, doctors] = await Promise.all([
    getSpecialties(),
    searchServices(),
    searchDoctors(),
  ]);
  const featured = featuredDoctors(doctors, specialties);
  return (
    <main>
      <Hero services={services} />
      <SpecialtiesSection specialties={specialties} serviceCount={services.length} />
      <StepsSection />
      <AssistantSection />
      <DoctorsSection doctors={featured} />
      <InfoSection />
    </main>
  );
}

function Hero({ services }: { services: Service[] }) {
  const status = openStatus();
  return (
    <section className="bg-linear-to-b from-surface to-ground">
      <div
        className={`${WRAP} grid items-center gap-8 pt-5 pb-10 md:pt-14 md:pb-16 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)] lg:gap-12`}
      >
        <div className="flex flex-col gap-4 md:gap-5">
          <span className="self-start rounded-full bg-primary-soft px-3 py-1 text-sm font-semibold text-primary-ink max-md:hidden">
            {TEXT.home.eyebrow}
          </span>
          <h1 className="text-[28px] leading-9 font-bold tracking-[-0.02em] md:text-[32px] md:leading-10 lg:text-[46px] lg:leading-[56px]">
            <span className="md:hidden">{TEXT.home.titleMobile}</span>
            <span className="max-md:hidden">{TEXT.home.title}</span>
          </h1>
          <p className="max-w-[34em] text-muted md:text-lg md:leading-7">
            <span className="md:hidden">{TEXT.home.leadMobile}</span>
            <span className="max-md:hidden">{TEXT.home.lead}</span>
          </p>
          <SearchForm placeholder={TEXT.home.searchPlaceholderShort} />
          <p className="-mt-2 text-sm text-muted max-md:hidden">
            {TEXT.home.suggestions}{" "}
            {TEXT.home.suggestionTerms.map((term, i) => (
              <span key={term}>
                {i > 0 ? " · " : null}
                <Link
                  href={`/services?q=${encodeURIComponent(term)}`}
                  className="text-primary hover:text-primary-hover"
                >
                  {term}
                </Link>
              </span>
            ))}
            . {TEXT.home.accentHint}
          </p>
          <div className="grid grid-cols-2 gap-2 md:flex md:flex-wrap md:gap-3">
            <Link href="/booking" className={buttonClass({ size: "lg" })}>
              {TEXT.nav.bookNow}
            </Link>
            <a href="#tro-ly" className={buttonClass({ variant: "outline", size: "lg" })}>
              <ChatIcon size={20} />
              {TEXT.home.askAssistant}
            </a>
          </div>
          <ul className="mt-1 flex flex-wrap gap-x-5 gap-y-2 text-sm text-muted max-md:hidden">
            {TEXT.home.perks.map((perk) => (
              <li key={perk} className="flex items-center gap-1.5">
                <CheckIcon size={16} strokeWidth={2.4} className="text-success" />
                {perk}
              </li>
            ))}
          </ul>
        </div>

        <div className="relative">
          <div className="relative h-[168px] overflow-hidden rounded-[14px] bg-[#dce8e7] md:h-[260px] md:rounded-[20px] lg:h-[480px]">
            <Image
              src="/images/hero.jpg"
              alt={TEXT.home.heroAlt}
              fill
              sizes="(min-width: 1024px) 560px, 100vw"
              loading="eager"
              fetchPriority="high"
              className="object-cover object-[62%_50%]"
            />
          </div>
          <span className="absolute top-2.5 left-2.5 flex items-center gap-2 rounded-full bg-surface px-3 py-1.5 text-xs font-semibold shadow-[0_4px_14px_rgba(19,38,43,0.12)] md:top-4 md:right-4 md:left-auto md:text-sm">
            <span
              aria-hidden="true"
              className={`size-2 rounded-full ${status.open ? "bg-success" : "bg-muted"}`}
            />
            {status.open && status.until ? TEXT.home.openNow(status.until) : TEXT.home.closedNow}
          </span>
          <NearestSlotCard
            services={services.map((s) => ({
              id: s.id,
              name: s.name,
              specialty: s.specialty.name,
            }))}
            className="relative z-10 mx-3 -mt-7 md:mx-4 md:-mt-9 lg:absolute lg:bottom-7 lg:-left-7 lg:mx-0 lg:mt-0 lg:w-[300px]"
          />
        </div>
      </div>
    </section>
  );
}

function SpecialtiesSection({
  specialties,
  serviceCount,
}: {
  specialties: Specialty[];
  serviceCount: number;
}) {
  return (
    <section id="chuyen-khoa" className={`${WRAP} pt-6 pb-4 md:pt-16`}>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3 md:mb-6">
        <div className="flex flex-col gap-1.5">
          <h2 className={H2}>{TEXT.home.specialtiesTitle(specialties.length, serviceCount)}</h2>
          <p className="text-muted max-md:hidden">{TEXT.home.specialtiesLead}</p>
        </div>
        <Link href="/services" className="font-semibold text-primary hover:text-primary-hover">
          {TEXT.home.allServices}
        </Link>
      </div>
      <ul className="grid grid-cols-2 gap-2.5 md:gap-4 lg:grid-cols-3">
        {specialties.map((specialty) => {
          const media = specialtyMedia(specialty.name);
          return (
            <li key={specialty.id}>
              <Link
                href={`/services?specialty=${specialty.id}`}
                className="flex h-full flex-col overflow-hidden rounded-card border border-line bg-surface transition-colors hover:border-primary"
              >
                <span className="relative block h-[92px] bg-[#dce8e7] md:h-[168px]">
                  <Image
                    src={media.src}
                    alt=""
                    fill
                    sizes="(min-width: 1024px) 380px, 50vw"
                    className="object-cover"
                    style={{ objectPosition: media.position }}
                  />
                </span>
                <span className="flex flex-1 flex-col gap-1 px-2.5 pt-2 pb-2.5 md:px-4 md:pt-3.5 md:pb-4">
                  <b className="text-[15px] md:text-lg md:leading-[26px]">{specialty.name}</b>
                  {specialty.description ? (
                    <span className="text-sm text-muted max-md:hidden">
                      {specialty.description}
                    </span>
                  ) : null}
                  <span className="mt-auto flex justify-between pt-1.5 text-xs text-muted md:text-sm md:text-ink">
                    <span>
                      {specialty.min_price_vnd !== null
                        ? TEXT.home.specialtyMeta(
                            specialty.service_count,
                            formatPrice(specialty.min_price_vnd),
                          )
                        : TEXT.booking.serviceCount(specialty.service_count)}
                    </span>
                    <span className="font-semibold text-primary max-md:hidden">
                      {TEXT.home.specialtyCta}
                    </span>
                  </span>
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function StepsSection() {
  return (
    <section className={`${WRAP} pt-10 pb-12 md:pt-14 md:pb-16`}>
      <h2 className={`${H2} mb-5`}>{TEXT.home.stepsTitle}</h2>
      <ol className="grid gap-4 md:grid-cols-3">
        {TEXT.home.steps.map((step, index) => (
          <li
            key={step.title}
            className="flex flex-col gap-2 rounded-card border border-line bg-surface p-5"
          >
            <span className="flex items-center gap-2.5">
              <span
                aria-hidden="true"
                className="flex size-9 items-center justify-center rounded-[10px] bg-primary-soft font-bold text-primary-ink"
              >
                {index + 1}
              </span>
              <b className="text-lg">{step.title}</b>
            </span>
            <span className="text-muted">{step.body}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}

function AssistantSection() {
  return (
    <section id="tro-ly" className="bg-primary-soft">
      <div
        className={`${WRAP} grid items-center gap-8 py-12 md:py-16 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)] lg:gap-12`}
      >
        <div className="relative h-[280px] overflow-hidden rounded-2xl bg-[#c9dedb] lg:h-[440px]">
          <Image
            src="/images/assistant.jpg"
            alt={TEXT.home.assistantAlt}
            fill
            sizes="(min-width: 1024px) 540px, 100vw"
            className="object-cover object-[38%_45%]"
          />
        </div>
        <div className="flex flex-col gap-4">
          <span className="self-start rounded-full bg-surface px-3 py-1 text-sm font-semibold text-primary-ink">
            {TEXT.home.assistantEyebrow}
          </span>
          <h2 className={H2}>{TEXT.home.assistantTitle}</h2>
          <p className="text-subtle">{TEXT.home.assistantBody}</p>
          <div aria-hidden="true" className="flex flex-col gap-2.5 rounded-card bg-surface p-4">
            <span className="max-w-[80%] self-end rounded-[14px_14px_4px_14px] bg-primary px-3.5 py-2.5 text-[15px] leading-[22px] text-white">
              Cho con tôi 5 tuổi khám nhi sáng thứ Bảy được không?
            </span>
            <span className="max-w-[86%] self-start rounded-[14px_14px_14px_4px] bg-[#f1f4f5] px-3.5 py-2.5 text-[15px] leading-[22px]">
              Được ạ. <b>Khám nhi tổng quát</b> dành cho trẻ dưới 16 tuổi, 20 phút, 220.000 ₫. Sáng
              Thứ Bảy, bác sĩ còn trống:
            </span>
            <span className="flex gap-2">
              {["08:40", "09:20"].map((time) => (
                <span
                  key={time}
                  className="rounded-control border border-primary px-3.5 py-1.5 font-semibold text-primary-ink tabular-nums"
                >
                  {time}
                </span>
              ))}
            </span>
          </div>
          <p className="flex items-start gap-2 rounded-control bg-surface/70 px-3.5 py-3 text-sm text-subtle">
            <ChatIcon size={18} className="mt-0.5 shrink-0 text-primary" />
            {TEXT.home.assistantSoon}
          </p>
          <p className="text-[13px] leading-[19px] text-subtle">{TEXT.home.assistantNote}</p>
        </div>
      </div>
    </section>
  );
}

function DoctorsSection({ doctors }: { doctors: Doctor[] }) {
  const serviceIds = doctors
    .map((d) => earliestServiceOf(d))
    .filter((id): id is number => id !== undefined);
  return (
    <section className={`${WRAP} pt-12 pb-4 md:pt-16`}>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-col gap-1.5">
          <h2 className={H2}>{TEXT.home.doctorsTitle}</h2>
          <p className="text-muted">{TEXT.home.doctorsLead}</p>
        </div>
        <Link
          href="/services?tab=doctors"
          className="font-semibold text-primary hover:text-primary-hover"
        >
          {TEXT.home.allDoctors}
        </Link>
      </div>
      <ul className="flex snap-x snap-mandatory gap-4 overflow-x-auto pb-1 md:grid md:grid-cols-2 md:overflow-visible lg:grid-cols-4">
        {doctors.map((doctor) => (
          <li key={doctor.id} className="shrink-0 basis-[232px] snap-start md:basis-auto">
            <DoctorCard doctor={doctor} serviceIds={serviceIds} className="h-full" />
          </li>
        ))}
      </ul>
    </section>
  );
}

function InfoSection() {
  const missing = <span className="text-muted">{TEXT.home.toBeUpdated}</span>;
  return (
    <section
      id="lien-he"
      className={`${WRAP} grid items-start gap-8 pt-12 pb-16 md:grid-cols-2 md:pt-16 md:pb-20`}
    >
      <div className="flex flex-col gap-[18px] rounded-card border border-line bg-surface p-5">
        <div className="grid grid-cols-[2fr_1fr] gap-2.5">
          <div className="relative h-[200px] overflow-hidden rounded-[10px] bg-[#dce8e7]">
            <Image
              src="/images/clinic.jpg"
              alt={TEXT.home.clinicAlt}
              fill
              sizes="(min-width: 768px) 380px, 66vw"
              className="object-cover object-[40%_55%]"
            />
          </div>
          <div className="relative h-[200px] overflow-hidden rounded-[10px] bg-[#dce8e7]">
            <Image
              src="/images/reception.jpg"
              alt={TEXT.home.receptionAlt}
              fill
              sizes="(min-width: 768px) 190px, 33vw"
              className="object-cover object-[55%_40%]"
            />
          </div>
        </div>
        <h2 className="text-2xl leading-8 font-bold">{TEXT.home.infoTitle}</h2>
        <dl className="grid grid-cols-[110px_minmax(0,1fr)] gap-x-4 gap-y-2.5 text-[15px] leading-[22px] md:grid-cols-[120px_minmax(0,1fr)]">
          <dt className="text-muted">{TEXT.home.infoAddress}</dt>
          <dd>{CLINIC.address || missing}</dd>
          <dt className="text-muted">{TEXT.home.infoHours}</dt>
          <dd>
            {CLINIC.openingHoursText.map((line) => (
              <span key={line} className="block">
                {line}
              </span>
            ))}
          </dd>
          <dt className="text-muted">{TEXT.home.infoPhone}</dt>
          <dd>{CLINIC.phone || missing}</dd>
          <dt className="text-muted">{TEXT.home.infoPayment}</dt>
          <dd>{TEXT.home.paymentText}</dd>
        </dl>
      </div>
      <div className="flex flex-col gap-2.5">
        <h2 className="mb-1.5 text-2xl leading-8 font-bold">{TEXT.home.faqTitle}</h2>
        {TEXT.home.faq.map((item, index) => (
          <details
            key={item.q}
            open={index === 0}
            className="group rounded-card border border-line bg-surface"
          >
            <summary className="flex cursor-pointer list-none justify-between gap-3 px-4 py-3.5 font-semibold [&::-webkit-details-marker]:hidden">
              {item.q}
              <ChevronDownIcon
                size={20}
                className="shrink-0 text-muted transition-transform group-open:rotate-180"
              />
            </summary>
            <p className="px-4 pb-4 text-muted">{item.a}</p>
          </details>
        ))}
      </div>
    </section>
  );
}
