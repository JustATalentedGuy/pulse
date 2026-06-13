import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';

import { api } from '@/api/client';
import { useFeedStore } from '@/store/feedStore';
import { shouldRecordRead } from '@/utils/articles';

export function useReadTimer(articleId: string) {
  const queryClient = useQueryClient();
  const startReadTimer = useFeedStore((state) => state.startReadTimer);
  const stopReadTimer = useFeedStore((state) => state.stopReadTimer);
  const { mutate: recordRead } = useMutation({
    mutationFn: (durationSeconds: number) =>
      api.post(`/feed/${articleId}/read`, {
        duration_seconds: durationSeconds,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['article', articleId] });
      queryClient.invalidateQueries({ queryKey: ['feed'] });
    },
  });

  useEffect(() => {
    startReadTimer(articleId);
    return () => {
      const duration = stopReadTimer(articleId);
      if (shouldRecordRead(duration)) {
        recordRead(duration);
      }
    };
  }, [articleId, recordRead, startReadTimer, stopReadTimer]);
}
