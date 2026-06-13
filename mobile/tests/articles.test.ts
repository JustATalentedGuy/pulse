import {
  articleStaggerDelay,
  shouldRecordRead,
  uniqueArticles,
} from '@/utils/articles';
import type { Article } from '@/types/article';

function article(id: string): Article {
  return {
    id,
    title: id,
    url: `https://example.com/${id}`,
    source: 'test',
    source_domain: 'example.com',
    published_at: null,
    ingested_at: '2026-06-12T00:00:00Z',
    summary: 'summary',
    category: 'tools',
    importance: 3,
    entities: { models: [], companies: [], techniques: [], datasets: [] },
    keywords: [],
    bookmarked: false,
    read_at: null,
    read_duration_s: null,
    quiz_attempted: false,
    personalized_score: 1,
  };
}

test('read tracking enforces the five second threshold', () => {
  expect(shouldRecordRead(4)).toBe(false);
  expect(shouldRecordRead(5)).toBe(true);
  expect(shouldRecordRead(10)).toBe(true);
});

test('infinite pages are flattened without duplicate article IDs', () => {
  expect(
    uniqueArticles([
      { items: [article('a'), article('b')] },
      { items: [article('b'), article('c')] },
    ]).map((item) => item.id),
  ).toEqual(['a', 'b', 'c']);
});

test('article stagger is 40ms per card and capped at 400ms', () => {
  expect(articleStaggerDelay(0)).toBe(0);
  expect(articleStaggerDelay(9)).toBe(360);
  expect(articleStaggerDelay(20)).toBe(400);
});
