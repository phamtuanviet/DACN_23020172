"use client";

// Gọi API của khu vực quản trị (docs mục 8.2, 9.4). Lịch hẹn và hàng chờ tự tải lại mỗi 60 giây;
// sau mỗi thao tác ghi thì làm mới dữ liệu liên quan, kể cả khung trống của trang công khai.
import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
} from "@tanstack/react-query";

import { api } from "@/shared/api/client";
import { toApiError } from "@/shared/api/errors";
import type { components } from "@/shared/api/schema";
import type {
  AdminAppointment,
  AdminAppointmentPage,
  AppointmentStatus,
  Channel,
  DoctorAdmin,
  ServiceAdmin,
  Shift,
  SpecialtyAdmin,
  SupportRequest,
  TimeOff,
} from "@/shared/api/types";
import { refreshAfterChange } from "@/shared/appointments/queries";

type Schemas = components["schemas"];
const REFRESH_MS = 60_000;
export const PAGE_SIZE = 20;

// ---------------------------------------------------------------------------- lịch hẹn
export type AppointmentFilters = {
  dateFrom?: string;
  dateTo?: string;
  doctorId?: number;
  status?: AppointmentStatus;
  channel?: Channel;
  needsAttention?: boolean;
  q?: string;
  page: number;
  pageSize?: number;
};

export function useAdminAppointments(filters: AppointmentFilters) {
  return useQuery({
    queryKey: ["admin", "appointments", filters],
    placeholderData: keepPreviousData,
    refetchInterval: REFRESH_MS,
    queryFn: async (): Promise<AdminAppointmentPage> => {
      const { data, error } = await api.GET("/api/v1/admin/appointments", {
        params: {
          query: {
            date_from: filters.dateFrom,
            date_to: filters.dateTo,
            doctor_id: filters.doctorId,
            status: filters.status,
            channel: filters.channel,
            needs_attention: filters.needsAttention,
            q: filters.q || undefined,
            page: filters.page,
            page_size: filters.pageSize ?? PAGE_SIZE,
          },
        },
      });
      if (!data) throw toApiError(error);
      return data;
    },
  });
}

export function useSetAttention() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (input: { id: number; value: boolean }): Promise<AdminAppointment> => {
      const { data, error } = await api.PATCH(
        "/api/v1/admin/appointments/{appointment_id}/attention",
        {
          params: { path: { appointment_id: input.id } },
          body: { needs_attention: input.value },
        },
      );
      if (!data) throw toApiError(error);
      return data;
    },
    onSettled: () => refreshAfterChange(client),
  });
}

export function useChangeStatus() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (input: { id: number; status: Schemas["StatusChangeRequest"]["status"] }) => {
      const { data, error } = await api.PATCH("/api/v1/appointments/{appointment_id}/status", {
        params: { path: { appointment_id: input.id } },
        body: { status: input.status },
      });
      if (!data) throw toApiError(error);
      return data;
    },
    onSettled: () => refreshAfterChange(client),
  });
}

// ---------------------------------------------------------------------------- hỗ trợ
export function useSupportRequests(status: "OPEN" | "DONE") {
  return useQuery({
    queryKey: ["admin", "support", status],
    refetchInterval: REFRESH_MS,
    queryFn: async (): Promise<SupportRequest[]> => {
      const { data, error } = await api.GET("/api/v1/admin/support-requests", {
        params: { query: { status } },
      });
      if (!data) throw toApiError(error);
      return data;
    },
  });
}

export function useUpdateSupportRequest() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (input: { id: number; status: "OPEN" | "DONE" }) => {
      const { data, error } = await api.PATCH("/api/v1/admin/support-requests/{request_id}", {
        params: { path: { request_id: input.id } },
        body: { status: input.status },
      });
      if (!data) throw toApiError(error);
      return data;
    },
    onSettled: () => client.invalidateQueries({ queryKey: ["admin"] }),
  });
}

// ---------------------------------------------------------------------------- danh mục
export function useAdminSpecialties() {
  return useQuery({
    queryKey: ["admin", "catalog", "specialties"],
    queryFn: async (): Promise<SpecialtyAdmin[]> => {
      const { data, error } = await api.GET("/api/v1/admin/specialties");
      if (!data) throw toApiError(error);
      return data;
    },
  });
}

export function useAdminServices() {
  return useQuery({
    queryKey: ["admin", "catalog", "services"],
    queryFn: async (): Promise<ServiceAdmin[]> => {
      const { data, error } = await api.GET("/api/v1/admin/services");
      if (!data) throw toApiError(error);
      return data;
    },
  });
}

function refreshCatalog(client: QueryClient): Promise<unknown> {
  return Promise.all([
    client.invalidateQueries({ queryKey: ["admin", "catalog"] }),
    client.invalidateQueries({ queryKey: ["admin", "doctors"] }),
    client.invalidateQueries({ queryKey: ["catalog"] }),
    client.invalidateQueries({ queryKey: ["availability"] }),
  ]);
}

export type SpecialtyInput = Schemas["SpecialtyCreate"] & { is_active?: boolean };

export function useSaveSpecialty() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (input: { id?: number; body: SpecialtyInput }): Promise<SpecialtyAdmin> => {
      const result = input.id
        ? await api.PATCH("/api/v1/admin/specialties/{specialty_id}", {
            params: { path: { specialty_id: input.id } },
            body: input.body,
          })
        : await api.POST("/api/v1/admin/specialties", { body: input.body });
      if (!result.data) throw toApiError(result.error);
      return result.data;
    },
    onSettled: () => refreshCatalog(client),
  });
}

export type ServiceInput = Schemas["ServiceCreate"] & { is_active?: boolean };

export function useSaveService() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (input: { id?: number; body: ServiceInput }): Promise<ServiceAdmin> => {
      const result = input.id
        ? await api.PATCH("/api/v1/admin/services/{service_id}", {
            params: { path: { service_id: input.id } },
            body: input.body,
          })
        : await api.POST("/api/v1/admin/services", { body: input.body });
      if (!result.data) throw toApiError(result.error);
      return result.data;
    },
    onSettled: () => refreshCatalog(client),
  });
}

// ---------------------------------------------------------------------------- bác sĩ
export function useAdminDoctors() {
  return useQuery({
    queryKey: ["admin", "doctors"],
    queryFn: async (): Promise<DoctorAdmin[]> => {
      const { data, error } = await api.GET("/api/v1/admin/doctors");
      if (!data) throw toApiError(error);
      return data;
    },
  });
}

export function useCreateDoctor() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: Schemas["DoctorCreate"]): Promise<DoctorAdmin> => {
      const { data, error } = await api.POST("/api/v1/admin/doctors", { body });
      if (!data) throw toApiError(error);
      return data;
    },
    onSettled: () => refreshCatalog(client),
  });
}

export function useUpdateDoctor() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      id: number;
      body: Schemas["DoctorUpdate"];
    }): Promise<DoctorAdmin> => {
      const { data, error } = await api.PATCH("/api/v1/admin/doctors/{doctor_id}", {
        params: { path: { doctor_id: input.id } },
        body: input.body,
      });
      if (!data) throw toApiError(error);
      return data;
    },
    onSettled: () => refreshCatalog(client),
  });
}

// ---------------------------------------------------------------------------- ca làm, ngày nghỉ
export function useShifts(doctorId: number | undefined) {
  return useQuery({
    queryKey: ["admin", "shifts", doctorId],
    enabled: doctorId !== undefined,
    queryFn: async (): Promise<Shift[]> => {
      const { data, error } = await api.GET("/api/v1/admin/doctors/{doctor_id}/shifts", {
        params: { path: { doctor_id: doctorId ?? 0 } },
      });
      if (!data) throw toApiError(error);
      return data;
    },
  });
}

export function useTimeOffs(doctorId: number | undefined, since: string) {
  return useQuery({
    queryKey: ["admin", "time-offs", doctorId, since],
    enabled: doctorId !== undefined,
    queryFn: async (): Promise<TimeOff[]> => {
      const { data, error } = await api.GET("/api/v1/admin/doctors/{doctor_id}/time-offs", {
        params: { path: { doctor_id: doctorId ?? 0 }, query: { since } },
      });
      if (!data) throw toApiError(error);
      return data;
    },
  });
}

export type ShiftInput = Schemas["ShiftIn"];

/** Thêm ca (không ảnh hưởng lịch đã đặt), sửa hoặc xóa ca (`dryRun` liệt kê lịch bị ảnh hưởng). */
export function useShiftChange() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (
      input:
        | { kind: "create"; doctorId: number; body: ShiftInput }
        | { kind: "update"; doctorId: number; shiftId: number; body: ShiftInput; dryRun: boolean }
        | { kind: "delete"; doctorId: number; shiftId: number; dryRun: boolean },
    ): Promise<Schemas["ShiftChangeOut"]> => {
      if (input.kind === "create") {
        const { data, error } = await api.POST("/api/v1/admin/doctors/{doctor_id}/shifts", {
          params: { path: { doctor_id: input.doctorId } },
          body: input.body,
        });
        if (!data) throw toApiError(error);
        return { dry_run: false, shift: data, affected: [] };
      }
      const path = { doctor_id: input.doctorId, shift_id: input.shiftId };
      const query = { dry_run: input.dryRun };
      const result =
        input.kind === "update"
          ? await api.PATCH("/api/v1/admin/doctors/{doctor_id}/shifts/{shift_id}", {
              params: { path, query },
              body: input.body,
            })
          : await api.DELETE("/api/v1/admin/doctors/{doctor_id}/shifts/{shift_id}", {
              params: { path, query },
            });
      if (!result.data) throw toApiError(result.error);
      return result.data;
    },
    onSettled: (data) => (data?.dry_run ? undefined : refreshAfterChange(client)),
  });
}

export function useCreateTimeOff() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      doctorId: number;
      body: Schemas["TimeOffIn"];
      dryRun: boolean;
    }): Promise<Schemas["TimeOffChangeOut"]> => {
      const { data, error } = await api.POST("/api/v1/admin/doctors/{doctor_id}/time-offs", {
        params: { path: { doctor_id: input.doctorId }, query: { dry_run: input.dryRun } },
        body: input.body,
      });
      if (!data) throw toApiError(error);
      return data;
    },
    onSettled: (data) => (data?.dry_run ? undefined : refreshAfterChange(client)),
  });
}

export function useDeleteTimeOff() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (input: { doctorId: number; timeOffId: number }) => {
      const { error, response } = await api.DELETE(
        "/api/v1/admin/doctors/{doctor_id}/time-offs/{time_off_id}",
        { params: { path: { doctor_id: input.doctorId, time_off_id: input.timeOffId } } },
      );
      if (!response.ok) throw toApiError(error);
    },
    onSettled: () => refreshAfterChange(client),
  });
}
