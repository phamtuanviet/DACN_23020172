// Khung tạm cho màn hình chưa làm; thay bằng component thật của feature tương ứng.
export function PagePlaceholder({ title, description }: { title: string; description?: string }) {
  return (
    <main className="mx-auto max-w-5xl px-4 py-10">
      <h1 className="text-2xl font-semibold">{title}</h1>
      {description ? <p className="mt-2 text-gray-600">{description}</p> : null}
    </main>
  );
}
