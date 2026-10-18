"use client";

// Lịch hẹn của bệnh nhân: dùng chung cho wizard đặt lịch, trang đặt thành công và Lịch của tôi
// (docs mục 9.4). Sau mỗi lần đặt, đổi, hủy thì làm mới cả lịch hẹn lẫn khung trống.
import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
} from "@tanstack/react-query";

import { api } from "@/shared/api/client";
import { toApiError } from "@/shared/api/errors";
import type {
  Appointment,
  AppointmentDetail,
  AppointmentPage,
  AppointmentScope,
  AppointmentStatus,
} from "@/shared/api/types";

const PAGE_SIZE = 20;

/** Lịch sắp tới hoặc lịch sử, tải thêm từng trang 20 lịch (docs mục 8.1). */
export function useMyAppointmentList(scope: AppointmentScope, status?: AppointmentStatus) {
  return useInfiniteQuery({
    queryKey: ["appointments", "me", { scope, status }],
    initialPageParam: 1,
    queryFn: async ({ pageParam }): Promise<AppointmentPage> => {
      const { data, error } = await api.GET("/api/v1/appointments/me", {
        params: { query: { scope, status, page: pageParam, page_size: PAGE_SIZE } },
      });
      if (!data) throw toApiError(error);
      return data;
    },
    getNextPageParam: (last) =>
      last.page * last.page_size < last.total ? last.page + 1 : undefined,
  });
}

export function useAppointment(id: number | undefined) {
  return useQuery({
    queryKey: ["appointments", "detail", id],
    enabled: id !== undefined,
    queryFn: async (): Promise<AppointmentDetail> => {
      const { data, error } = await api.GET("/api/v1/appointments/{appointment_id}", {
        params: { path: { appointment_id: id ?? 0 } },
      });
      if (!data) throw toApiError(error);
      return data;
    },
  });
}

/** Lịch hẹn và khung trống cùng đổi sau mỗi thao tác ghi. */
export function refreshAfterChange(client: QueryClient): Promise<unknown> {
  return Promise.all([
    client.invalidateQueries({ queryKey: ["appointments"] }),
    client.invalidateQueries({ queryKey: ["availability"] }),
  ]);
}

export type BookInput = {
  serviceId: number;
  /** null: bác sĩ bất kỳ */
  doctorId: number | null;
  startAt: string;
  reason?: string;
};

export function useBookAppointment() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (input: BookInput): Promise<Appointment> => {
      const { data, error } = await api.POST("/api/v1/appointments", {
        body: {
          service_id: input.serviceId,
          doctor_id: input.doctorId,
          start_at: input.startAt,
          reason: input.reason?.trim() || null,
        },
      });
      if (!data) throw toApiError(error);
      return data;
    },
    onSettled: () => refreshAfterChange(client),
  });
}

export function useRescheduleAppointment() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      id: number;
      doctorId: number;
      startAt: string;
    }): Promise<Appointment> => {
      const { data, error } = await api.PATCH("/api/v1/appointments/{appointment_id}/reschedule", {
        params: { path: { appointment_id: input.id } },
        body: { start_at: input.startAt, doctor_id: input.doctorId },
      });
      if (!data) throw toApiError(error);
      return data;
    },
    onSettled: () => refreshAfterChange(client),
  });
}

export function useCancelAppointment() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (input: { id: number; reason?: string }): Promise<Appointment> => {
      const { data, error } = await api.POST("/api/v1/appointments/{appointment_id}/cancel", {
        params: { path: { appointment_id: input.id } },
        body: { reason: input.reason?.trim() || null },
      });
      if (!data) throw toApiError(error);
      return data;
    },
    onSettled: () => refreshAfterChange(client),
  });
}
