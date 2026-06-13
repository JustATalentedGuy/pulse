import { useMutation } from '@tanstack/react-query';

import { api } from '@/api/client';
import type {
  AskResponse,
  ConversationMessage,
} from '@/types/phase8';

export function useAsk() {
  return useMutation({
    mutationFn: async ({
      question,
      conversationHistory,
    }: {
      question: string;
      conversationHistory: ConversationMessage[];
    }) => {
      const response = await api.post<AskResponse>(
        '/ask',
        {
          question,
          conversation_history: conversationHistory.slice(-6),
        },
        { timeout: 120_000 },
      );
      return response.data;
    },
  });
}
