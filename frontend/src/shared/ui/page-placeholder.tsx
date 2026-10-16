// Khung tạm cho màn hình của sprint sau; thay bằng component thật của feature tương ứng.
import { TEXT } from "@/shared/texts";

import { Card } from "./card";
import { ToolsIcon } from "./icons";

export function PagePlaceholder({
  title,
  description,
  sprint,
}: {
  title: string;
  description?: string;
  sprint?: number;
}) {
  return (
    <main className="mx-auto w-full max-w-5xl px-4 py-8 md:px-6 md:py-10">
      <h1 className="text-2xl font-semibold md:text-[28px] md:leading-9">{title}</h1>
      <Card className="mt-5 flex flex-col items-center gap-3 px-6 py-12 text-center">
        <span
          aria-hidden="true"
          className="flex size-12 items-center justify-center rounded-full bg-primary-soft text-primary"
        >
          <ToolsIcon size={24} />
        </span>
        <p className="font-semibold">{TEXT.common.underConstruction}</p>
        <p className="max-w-md text-muted">
          {sprint ? TEXT.common.plannedIn(sprint) : null} {description}
        </p>
      </Card>
    </main>
  );
}
