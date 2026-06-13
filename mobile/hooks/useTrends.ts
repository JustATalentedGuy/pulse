import { useQuery } from '@tanstack/react-query';

import { api } from '@/api/client';
import type { Trend } from '@/types/phase8';

export function useTrends() {
  return useQuery({
    queryKey: ['trends'],
    queryFn: async () => {
      const response = await api.get<Trend[]>('/trends');
      return response.data;
    },
    staleTime: 30 * 60_000,
  });
}
