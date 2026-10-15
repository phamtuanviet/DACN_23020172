// Health check cho Caddy và Docker (docs mục 11.3). Không phải API nghiệp vụ.
export const dynamic = "force-dynamic";

export function GET() {
  return Response.json({ status: "ok" });
}
