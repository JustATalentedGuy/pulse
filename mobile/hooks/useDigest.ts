import { useQuery } from '@tanstack/react-query';

import { api } from '@/api/client';
import type { Digest } from '@/types/article';

export function useDigest(date = 'today') {
  return useQuery({
    queryKey: ['digest', date],
    queryFn: async () => {
      const response = await api.get<Digest>(`/digest/${date}`);
      return response.data;
    },
    retry: false,
    staleTime: 5 * 60_000,
  });
}
