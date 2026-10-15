"use client";

export default function ErrorPage({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <main className="mx-auto max-w-xl px-4 py-16 text-center">
      <h1 className="text-2xl font-semibold">Hệ thống đang gặp sự cố</h1>
      <p className="mt-2 text-gray-600">Vui lòng thử lại sau ít phút.</p>
      <button type="button" onClick={reset} className="mt-4 rounded bg-blue-700 px-4 py-2 text-white">
        Thử lại
      </button>
    </main>
  );
}
