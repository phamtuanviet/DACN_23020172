// Ghép class Tailwind có điều kiện: cn("a", isActive && "b") → "a b".
export function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}
