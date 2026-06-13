import type { InfiniteData } from '@tanstack/react-query';

import { updateFeedArticle } from '@/hooks/useArticleActions';
import type { Article, FeedResponse } from '@/types/article';

const article = {
  id: 'hidden',
  title: 'Hidden article',
} as Article;

test('optimistic hide removes the article from cached feed pages', () => {
  const data: InfiniteData<FeedResponse> = {
    pageParams: [0],
    pages: [
      {
        items: [article, { ...article, id: 'visible' }],
        total: 2,
        has_more: false,
        next_offset: 2,
      },
    ],
  };
  const updated = updateFeedArticle(data, 'hidden', () => null);
  expect(updated?.pages[0].items.map((item) => item.id)).toEqual(['visible']);
});
