"use client";

// Danh mục cho wizard (client component sau đăng nhập, docs mục 9.4). Danh mục ít đổi nên giữ
// "mới" trong 5 phút, cùng thời gian cache của trang công khai.
import { useQuery } from "@tanstack/react-query";

import { api } from "@/shared/api/client";
import { toApiError } from "@/shared/api/errors";
import type { Doctor, Service, Specialty } from "@/shared/api/types";

const CATALOG_STALE_MS = 5 * 60 * 1000;

export function useSpecialties() {
  return useQuery({
    queryKey: ["catalog", "specialties"],
    staleTime: CATALOG_STALE_MS,
    queryFn: async (): Promise<Specialty[]> => {
      const { data, error } = await api.GET("/api/v1/specialties");
      if (!data) throw toApiError(error);
      return data;
    },
  });
}

export function useServices(filters: { q?: string; specialtyId?: number }, enabled = true) {
  return useQuery({
    queryKey: ["catalog", "services", filters],
    staleTime: CATALOG_STALE_MS,
    enabled,
    queryFn: async (): Promise<Service[]> => {
      const { data, error } = await api.GET("/api/v1/services", {
        params: { query: { q: filters.q || undefined, specialty_id: filters.specialtyId } },
      });
      if (!data) throw toApiError(error);
      return data;
    },
  });
}

export function useDoctorsOfService(serviceId: number | undefined) {
  return useQuery({
    queryKey: ["catalog", "doctors", { serviceId }],
    staleTime: CATALOG_STALE_MS,
    enabled: serviceId !== undefined,
    queryFn: async (): Promise<Doctor[]> => {
      const { data, error } = await api.GET("/api/v1/doctors", {
        params: { query: { service_id: serviceId } },
      });
      if (!data) throw toApiError(error);
      return data;
    },
  });
}
