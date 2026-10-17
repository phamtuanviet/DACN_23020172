// Đọc danh mục từ server component (render phía server, cache 5 phút, docs mục 9.1).
// Lỗi mạng hoặc 5xx ném ra để error.tsx hiện thông báo chung; 404 của hồ sơ bác sĩ trả null.
import { catalogApi } from "@/shared/api/server";
import type { Doctor, DoctorDetail, Service, Specialty } from "@/shared/api/types";

function failed(what: string): Error {
  return new Error(`Không tải được ${what}`);
}

export async function getSpecialties(): Promise<Specialty[]> {
  const { data } = await catalogApi().GET("/api/v1/specialties");
  if (!data) throw failed("chuyên khoa");
  return data;
}

export async function searchServices(
  filters: { q?: string; specialtyId?: number } = {},
): Promise<Service[]> {
  const { data } = await catalogApi().GET("/api/v1/services", {
    params: { query: { q: filters.q || undefined, specialty_id: filters.specialtyId } },
  });
  if (!data) throw failed("dịch vụ");
  return data;
}

export async function searchDoctors(
  filters: { q?: string; specialtyId?: number; serviceId?: number } = {},
): Promise<Doctor[]> {
  const { data } = await catalogApi().GET("/api/v1/doctors", {
    params: {
      query: {
        q: filters.q || undefined,
        specialty_id: filters.specialtyId,
        service_id: filters.serviceId,
      },
    },
  });
  if (!data) throw failed("bác sĩ");
  return data;
}

export async function getDoctor(id: number): Promise<DoctorDetail | null> {
  const { data, response } = await catalogApi().GET("/api/v1/doctors/{doctor_id}", {
    params: { path: { doctor_id: id } },
  });
  if (response.status === 404) return null;
  if (!data) throw failed("hồ sơ bác sĩ");
  return data;
}
