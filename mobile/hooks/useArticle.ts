import { useQuery } from '@tanstack/react-query';

import { api } from '@/api/client';
import type { Article } from '@/types/article';

export function useArticle(id: string) {
  return useQuery({
    queryKey: ['article', id],
    queryFn: async () => {
      const response = await api.get<Article>(`/feed/${id}`);
      return response.data;
    },
    enabled: Boolean(id),
  });
}
