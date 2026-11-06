"use client";

// Gọi API của khu vực bác sĩ (docs mục 8.2, 9.4): lịch khám tự tải lại mỗi 60 giây và khi quay lại
// tab; đổi trạng thái, lưu ghi chú xong thì làm mới lịch khám và chi tiết lịch hẹn.
import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";

import { api } from "@/shared/api/client";
import { toApiError } from "@/shared/api/errors";
import type { components } from "@/shared/api/schema";
import type { AppointmentDetail, DoctorSchedule } from "@/shared/api/types";

const REFRESH_MS = 60_000;

export function useDoctorSchedule(dateFrom: string, dateTo: string) {
  return useQuery({
    queryKey: ["doctor", "schedule", { dateFrom, dateTo }],
    refetchInterval: REFRESH_MS,
    queryFn: async (): Promise<DoctorSchedule> => {
      const { data, error } = await api.GET("/api/v1/doctor/schedule", {
        params: { query: { date_from: dateFrom, date_to: dateTo } },
      });
      if (!data) throw toApiError(error);
      return data;
    },
  });
}

function refresh(client: QueryClient): Promise<unknown> {
  return Promise.all([
    client.invalidateQueries({ queryKey: ["doctor"] }),
    client.invalidateQueries({ queryKey: ["appointments"] }),
  ]);
}

export type VisitStatus = components["schemas"]["StatusChangeRequest"]["status"];

export function useSetVisitStatus() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (input: { id: number; status: VisitStatus }) => {
      const { data, error } = await api.PATCH("/api/v1/appointments/{appointment_id}/status", {
        params: { path: { appointment_id: input.id } },
        body: { status: input.status },
      });
      if (!data) throw toApiError(error);
      return data;
    },
    onSettled: () => refresh(client),
  });
}

export function useSaveNote() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (input: { id: number; note: string }): Promise<AppointmentDetail> => {
      const { data, error } = await api.PATCH("/api/v1/appointments/{appointment_id}/note", {
        params: { path: { appointment_id: input.id } },
        body: { note: input.note.trim() || null },
      });
      if (!data) throw toApiError(error);
      return data;
    },
    onSuccess: (detail) => client.setQueryData(["appointments", "detail", detail.id], detail),
    onSettled: () => refresh(client),
  });
}
