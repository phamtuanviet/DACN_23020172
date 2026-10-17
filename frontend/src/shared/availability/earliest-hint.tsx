"use client";

// Dòng "sớm nhất T6 16/10, 08:00" trên thẻ dịch vụ, thẻ bác sĩ, bước chọn bác sĩ.
import { formatSlot } from "@/shared/lib/datetime";
import { TEXT } from "@/shared/texts";

import { useEarliest } from "./queries";

type Props = {
  /** Mọi dịch vụ đang hiện trên trang: các thẻ dùng chung một request. */
  serviceIds: number[];
  serviceId: number;
  /** Có thì lấy khung sớm nhất của riêng bác sĩ này. */
  doctorId?: number;
  label?: string;
};

export function EarliestHint({ serviceIds, serviceId, doctorId, label }: Props) {
  const byDoctor = doctorId !== undefined;
  const { data, isPending, isError } = useEarliest(serviceIds, { byDoctor });
  if (isPending) {
    return <span className="inline-block h-4 w-28 animate-pulse rounded bg-divider align-middle" />;
  }
  if (isError) return null;
  const item = data.find(
    (i) => i.service_id === serviceId && (!byDoctor || i.doctor.id === doctorId),
  );
  if (!item) return <span className="text-muted">{TEXT.catalog.noSlot}</span>;
  return (
    <span>
      {label ?? TEXT.catalog.earliest}{" "}
      <b className="font-semibold tabular-nums">{formatSlot(item.start_at)}</b>
    </span>
  );
}
