import { useMutation, useQueryClient } from '@tanstack/react-query';

import { api } from '@/api/client';
import type {
  QuizAnswer,
  QuizGeneration,
  QuizSubmission,
} from '@/types/quiz';

export function useGenerateQuiz(articleId: string) {
  return useMutation({
    mutationFn: async () => {
      const response = await api.get<QuizGeneration>(
        `/quiz/generate/${articleId}`,
        { timeout: 60_000 },
      );
      return response.data;
    },
  });
}

export function useSubmitQuiz(articleId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      answers,
      durationSeconds,
    }: {
      answers: QuizAnswer[];
      durationSeconds: number;
    }) => {
      const response = await api.post<QuizSubmission>(
        `/quiz/${articleId}/submit`,
        {
          answers,
          duration_seconds: durationSeconds,
        },
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['article', articleId] });
      queryClient.invalidateQueries({ queryKey: ['feed'] });
    },
  });
}
