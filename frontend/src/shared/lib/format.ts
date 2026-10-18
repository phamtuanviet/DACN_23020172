// Định dạng giá, thời lượng, chữ viết tắt của họ tên.

const PRICE = new Intl.NumberFormat("vi-VN");

/** 250000 → "250.000 ₫" */
export function formatPrice(vnd: number): string {
  return `${PRICE.format(vnd)} ₫`;
}

export function formatDuration(minutes: number): string {
  return `${minutes} phút`;
}

/** "0912345678" → "0912 345 678"; số không đủ 10 chữ số giữ nguyên. */
export function formatPhone(phone: string | null | undefined): string {
  if (!phone) return "";
  return /^\d{10}$/.test(phone)
    ? `${phone.slice(0, 4)} ${phone.slice(4, 7)} ${phone.slice(7)}`
    : phone;
}

/** Bỏ dấu tiếng Việt, chữ thường: "Đa Liễu" → "da lieu" (so khớp tên chuyên khoa, tìm nhanh). */
export function unaccent(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/đ/g, "d")
    .replace(/Đ/g, "D")
    .toLowerCase();
}

/** Chữ viết tắt cho ảnh đại diện: bỏ học hàm ("ThS. BS.", "BS.CKI"), lấy hai từ cuối của tên.
 *  "ThS. BS. Trần Minh" → "TM", "BS.CKI Nguyễn Thu Hà" → "TH". */
export function initials(fullName: string): string {
  const words = fullName.split(/\s+/).filter((word) => word && !word.includes("."));
  return words
    .slice(-2)
    .map((word) => word.charAt(0).toLocaleUpperCase("vi"))
    .join("");
}

/** Tách phần "Không gồm …" của mô tả phạm vi khám để in đậm như thiết kế G-services. */
export function splitScope(scope: string): { included: string; excluded: string | null } {
  const index = scope.search(/Không gồm/i);
  if (index < 0) return { included: scope, excluded: null };
  return {
    included: scope.slice(0, index).trim(),
    excluded: scope
      .slice(index)
      .replace(/^Không gồm:?\s*/i, "")
      .trim(),
  };
}
