import { useInfiniteQuery } from '@tanstack/react-query';

import { api } from '@/api/client';
import type { FeedResponse } from '@/types/article';

export function useBookmarks() {
  return useInfiniteQuery({
    queryKey: ['bookmarks'],
    initialPageParam: 0,
    queryFn: async ({ pageParam }) => {
      const response = await api.get<FeedResponse>('/bookmarks', {
        params: { limit: 20, offset: pageParam },
      });
      return response.data;
    },
    getNextPageParam: (lastPage) =>
      lastPage.has_more ? lastPage.next_offset : undefined,
    staleTime: 30_000,
  });
}
