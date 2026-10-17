"use client";

// Khung trống luôn lấy mới từ trình duyệt, không cache ở server (TD-05, docs mục 9.4).
// Cùng query key thì TanStack Query gộp thành một request, nên nhiều thẻ trên trang dùng chung.
import { useQuery } from "@tanstack/react-query";

import { api } from "@/shared/api/client";
import { toApiError } from "@/shared/api/errors";
import type { Availability, EarliestItem } from "@/shared/api/types";

export type AvailabilityParams = {
  serviceId: number;
  doctorId?: number | null;
  dateFrom: string;
  dateTo: string;
};

export function useAvailability(params: AvailabilityParams | null) {
  return useQuery({
    queryKey: ["availability", params],
    enabled: params !== null,
    staleTime: 0,
    queryFn: async (): Promise<Availability> => {
      if (!params) throw new Error("Thiếu tham số");
      const { data, error } = await api.GET("/api/v1/availability", {
        params: {
          query: {
            service_id: params.serviceId,
            doctor_id: params.doctorId ?? undefined,
            date_from: params.dateFrom,
            date_to: params.dateTo,
          },
        },
      });
      if (!data) throw toApiError(error);
      return data;
    },
  });
}

/** Khung sớm nhất trong 30 ngày của các dịch vụ; `byDoctor` thì của từng bác sĩ. */
export function useEarliest(serviceIds: number[], { byDoctor = false } = {}) {
  const ids = [...new Set(serviceIds)].sort((a, b) => a - b);
  return useQuery({
    queryKey: ["availability", "earliest", ids, byDoctor],
    enabled: ids.length > 0,
    staleTime: 0,
    queryFn: async (): Promise<EarliestItem[]> => {
      const { data, error } = await api.GET("/api/v1/availability/earliest", {
        params: { query: { service_id: ids, by_doctor: byDoctor } },
      });
      if (!data) throw toApiError(error);
      return data.items;
    },
  });
}
