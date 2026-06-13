import type { Article } from '@/types/article';

export function uniqueArticles(pages: { items: Article[] }[]): Article[] {
  const seen = new Set<string>();
  return pages.flatMap((page) =>
    page.items.filter((article) => {
      if (seen.has(article.id)) return false;
      seen.add(article.id);
      return true;
    }),
  );
}

export function shouldRecordRead(durationSeconds: number): boolean {
  return durationSeconds >= 5;
}

export function articleStaggerDelay(index: number): number {
  return Math.min(index * 40, 400);
}
