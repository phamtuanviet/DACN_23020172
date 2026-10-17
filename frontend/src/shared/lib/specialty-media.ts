// Ảnh minh họa theo chuyên khoa (11 ảnh Pexels trong public/images, nguồn ở Design Direction).
// Chuyên khoa do quản trị thêm mà chưa có ảnh riêng thì dùng ảnh phòng khám.
import { unaccent } from "@/shared/lib/format";

export type SpecialtyMedia = { src: string; position: string };

const MEDIA: Record<string, SpecialtyMedia> = {
  "noi tong quat": { src: "/images/spec-internal.jpg", position: "55% 50%" },
  "da lieu": { src: "/images/spec-derm.jpg", position: "50% 50%" },
  nhi: { src: "/images/spec-pediatrics.jpg", position: "50% 28%" },
  "tai mui hong": { src: "/images/spec-ent.jpg", position: "60% 50%" },
  "rang ham mat": { src: "/images/spec-dental.jpg", position: "62% 40%" },
  mat: { src: "/images/spec-eye.jpg", position: "50% 45%" },
};

const FALLBACK: SpecialtyMedia = { src: "/images/clinic.jpg", position: "50% 50%" };

export function specialtyMedia(name: string): SpecialtyMedia {
  return MEDIA[unaccent(name).trim()] ?? FALLBACK;
}
