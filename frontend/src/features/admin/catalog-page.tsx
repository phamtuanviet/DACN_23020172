"use client";

// Danh mục của quản trị (AD-catalog, UC13): tab Chuyên khoa, Dịch vụ; bấm một dòng để sửa ở panel
// bên phải. Mục đã ẩn vẫn hiện ở đây (chữ xám) để hiện lại được; trang công khai cập nhật sau tối
// đa 5 phút do cache (docs mục 9.4), còn khung trống và đặt lịch đổi ngay.
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import type { ServiceAdmin, SpecialtyAdmin } from "@/shared/api/types";
import { cn } from "@/shared/lib/cn";
import { formatPrice } from "@/shared/lib/format";
import { TEXT } from "@/shared/texts";
import { Alert } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { PlusIcon } from "@/shared/ui/icons";

import { ServiceForm, SpecialtyForm } from "./catalog-forms";
import { useAdminServices, useAdminSpecialties } from "./queries";

const T = TEXT.admin;

type Editing =
  | { kind: "specialty"; item: SpecialtyAdmin | null }
  | { kind: "service"; item: ServiceAdmin | null }
  | null;

export function AdminCatalogPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const tab = searchParams.get("tab") === "specialties" ? "specialties" : "services";
  const specialties = useAdminSpecialties();
  const services = useAdminServices();
  const [editing, setEditing] = useState<Editing>(null);

  function switchTab(next: "specialties" | "services") {
    setEditing(null);
    router.replace(next === "services" ? pathname : `${pathname}?tab=specialties`, {
      scroll: false,
    });
  }

  const loading = specialties.isPending || services.isPending;
  const failed = specialties.isError || services.isError;

  return (
    <main className="mx-auto flex w-full max-w-[1280px] flex-col gap-4 px-4 py-6 md:px-7">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold md:text-[26px] md:leading-[34px]">
          {T.catalogTitle}
        </h1>
        <Button
          size="sm"
          onClick={() =>
            setEditing(
              tab === "services"
                ? { kind: "service", item: null }
                : { kind: "specialty", item: null },
            )
          }
        >
          <PlusIcon size={16} />
          {tab === "services" ? T.addService : T.addSpecialty}
        </Button>
      </div>
      <div role="tablist" aria-label={T.catalogTabs} className="flex gap-1 border-b border-line">
        {(["specialties", "services"] as const).map((value) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={tab === value}
            onClick={() => switchTab(value)}
            className={cn(
              "-mb-px h-10 border-b-2 px-3.5",
              tab === value
                ? "border-primary font-semibold text-primary-ink"
                : "border-transparent text-muted hover:text-ink",
            )}
          >
            {value === "specialties"
              ? T.specialtiesTab(specialties.data?.length ?? 0)
              : T.servicesTab(services.data?.length ?? 0)}
          </button>
        ))}
      </div>

      <div className="flex flex-col gap-5 lg:flex-row lg:items-start">
        <div className="min-w-0 flex-1">
          {loading ? (
            <span aria-hidden="true" className="block h-64 animate-pulse rounded-card bg-divider" />
          ) : failed ? (
            <Alert tone="danger">{T.loadError}</Alert>
          ) : tab === "services" ? (
            <ServiceTable
              items={services.data ?? []}
              selectedId={editing?.kind === "service" ? editing.item?.id : undefined}
              onEdit={(item) => setEditing({ kind: "service", item })}
            />
          ) : (
            <SpecialtyTable
              items={specialties.data ?? []}
              selectedId={editing?.kind === "specialty" ? editing.item?.id : undefined}
              onEdit={(item) => setEditing({ kind: "specialty", item })}
            />
          )}
        </div>
        {editing?.kind === "service" ? (
          <ServiceForm
            key={editing.item?.id ?? "new"}
            service={editing.item}
            specialties={specialties.data ?? []}
            onDone={() => setEditing(null)}
          />
        ) : editing?.kind === "specialty" ? (
          <SpecialtyForm
            key={editing.item?.id ?? "new"}
            specialty={editing.item}
            onDone={() => setEditing(null)}
          />
        ) : null}
      </div>
    </main>
  );
}

const HEAD = "border-b border-line px-3.5 py-2.5 text-left font-medium";
const CELL = "border-b border-divider px-3.5 py-3";

function Visibility({ active }: { active: boolean }) {
  return active ? (
    <span className="font-semibold text-success">{T.shown}</span>
  ) : (
    <span className="text-muted">{T.hidden}</span>
  );
}

function EditButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="text-left font-semibold text-ink hover:text-primary-ink hover:underline"
    >
      {label}
    </button>
  );
}

function ServiceTable({
  items,
  selectedId,
  onEdit,
}: {
  items: ServiceAdmin[];
  selectedId: number | undefined;
  onEdit: (item: ServiceAdmin) => void;
}) {
  const C = T.serviceColumns;
  return (
    <div className="overflow-x-auto rounded-card border border-line bg-surface">
      <table className="w-full min-w-[560px] border-collapse text-sm">
        <thead>
          <tr className="bg-[#f9fbfb] text-muted">
            <th scope="col" className={HEAD}>
              {C.name}
            </th>
            <th scope="col" className={HEAD}>
              {C.specialty}
            </th>
            <th scope="col" className={HEAD}>
              {C.duration}
            </th>
            <th scope="col" className={HEAD}>
              {C.price}
            </th>
            <th scope="col" className={HEAD}>
              {C.visible}
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr
              key={item.id}
              className={cn(
                item.id === selectedId && "bg-[#f4faf9]",
                !item.is_active && "text-muted",
              )}
            >
              <td className={CELL}>
                <EditButton label={item.name} onClick={() => onEdit(item)} />
              </td>
              <td className={CELL}>{item.specialty.name}</td>
              <td className={cn(CELL, "tabular-nums")}>{T.minutes(item.duration_min)}</td>
              <td className={cn(CELL, "tabular-nums")}>{formatPrice(item.ref_price_vnd)}</td>
              <td className={CELL}>
                <Visibility active={item.is_active} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SpecialtyTable({
  items,
  selectedId,
  onEdit,
}: {
  items: SpecialtyAdmin[];
  selectedId: number | undefined;
  onEdit: (item: SpecialtyAdmin) => void;
}) {
  const C = T.specialtyColumns;
  return (
    <div className="overflow-x-auto rounded-card border border-line bg-surface">
      <table className="w-full min-w-[480px] border-collapse text-sm">
        <thead>
          <tr className="bg-[#f9fbfb] text-muted">
            <th scope="col" className={HEAD}>
              {C.name}
            </th>
            <th scope="col" className={HEAD}>
              {C.services}
            </th>
            <th scope="col" className={HEAD}>
              {C.doctors}
            </th>
            <th scope="col" className={HEAD}>
              {C.visible}
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr
              key={item.id}
              className={cn(
                item.id === selectedId && "bg-[#f4faf9]",
                !item.is_active && "text-muted",
              )}
            >
              <td className={CELL}>
                <EditButton label={item.name} onClick={() => onEdit(item)} />
                {item.description ? (
                  <span className="mt-0.5 line-clamp-1 block text-muted">{item.description}</span>
                ) : null}
              </td>
              <td className={cn(CELL, "tabular-nums")}>{item.service_count}</td>
              <td className={cn(CELL, "tabular-nums")}>{item.doctor_count}</td>
              <td className={CELL}>
                <Visibility active={item.is_active} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
