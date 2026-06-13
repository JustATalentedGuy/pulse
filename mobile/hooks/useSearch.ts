import { useQuery } from '@tanstack/react-query';

import { api } from '@/api/client';
import type { SearchMode, SearchResponse } from '@/types/article';

export function useSearch(query: string, mode: SearchMode = 'hybrid') {
  const normalizedQuery = query.trim();
  return useQuery({
    queryKey: ['search', normalizedQuery, mode],
    queryFn: async () => {
      const response = await api.get<SearchResponse>('/search', {
        params: { q: normalizedQuery, mode, limit: 30 },
        timeout: mode === 'fts' ? 10_000 : 120_000,
      });
      return response.data;
    },
    enabled: normalizedQuery.length >= 2,
    staleTime: 60_000,
  });
}
