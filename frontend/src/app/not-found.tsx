import Link from "next/link";

export default function NotFound() {
  return (
    <main className="mx-auto max-w-xl px-4 py-16 text-center">
      <h1 className="text-2xl font-semibold">Không tìm thấy trang</h1>
      <Link href="/" className="mt-4 inline-block text-blue-700 underline">
        Về trang chủ
      </Link>
    </main>
  );
}
