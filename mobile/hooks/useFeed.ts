import { useInfiniteQuery } from '@tanstack/react-query';

import { api } from '@/api/client';
import type { CategoryKey, FeedResponse } from '@/types/article';

const PAGE_SIZE = 20;

export function useFeed(
  category: CategoryKey | null,
  minImportance = 1,
) {
  return useInfiniteQuery({
    queryKey: ['feed', category, minImportance],
    initialPageParam: 0,
    queryFn: async ({ pageParam }) => {
      const response = await api.get<FeedResponse>('/feed', {
        params: {
          category: category ?? undefined,
          min_importance: minImportance,
          limit: PAGE_SIZE,
          offset: pageParam,
        },
      });
      return response.data;
    },
    getNextPageParam: (lastPage) =>
      lastPage.has_more ? lastPage.next_offset : undefined,
    staleTime: 60_000,
  });
}
