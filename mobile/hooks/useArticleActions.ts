import {
  InfiniteData,
  useMutation,
  useQueryClient,
} from '@tanstack/react-query';

import { api } from '@/api/client';
import type { Article, FeedResponse, SearchResponse } from '@/types/article';

export function updateFeedArticle(
  data: InfiniteData<FeedResponse> | undefined,
  id: string,
  update: (article: Article) => Article | null,
) {
  if (!data) return data;
  return {
    ...data,
    pages: data.pages.map((page) => ({
      ...page,
      items: page.items.flatMap((article) => {
        if (article.id !== id) return [article];
        const updated = update(article);
        return updated ? [updated] : [];
      }),
    })),
  };
}

export function useArticleActions(article: Article) {
  const queryClient = useQueryClient();
  const bookmark = useMutation({
    mutationFn: () =>
      api.post<{ bookmarked: boolean }>(`/feed/${article.id}/bookmark`),
    onMutate: async () => {
      const bookmarked = !article.bookmarked;
      queryClient.setQueriesData<InfiniteData<FeedResponse>>(
        { queryKey: ['feed'] },
        (data) =>
          updateFeedArticle(data, article.id, (item) => ({
            ...item,
            bookmarked,
          })),
      );
      queryClient.setQueryData<Article>(
        ['article', article.id],
        (item) => item ? { ...item, bookmarked } : item,
      );
      return { bookmarked };
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['feed'] });
      queryClient.invalidateQueries({ queryKey: ['bookmarks'] });
      queryClient.invalidateQueries({ queryKey: ['article', article.id] });
    },
  });

  const hide = useMutation({
    mutationFn: () => api.post(`/feed/${article.id}/hide`),
    onMutate: async () => {
      queryClient.setQueriesData<InfiniteData<FeedResponse>>(
        { queryKey: ['feed'] },
        (data) => updateFeedArticle(data, article.id, () => null),
      );
      queryClient.setQueriesData<SearchResponse>(
        { queryKey: ['search'] },
        (data) =>
          data
            ? {
                ...data,
                results: data.results.filter((item) => item.id !== article.id),
              }
            : data,
      );
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['feed'] });
      queryClient.invalidateQueries({ queryKey: ['bookmarks'] });
      queryClient.invalidateQueries({ queryKey: ['search'] });
    },
  });

  return {
    toggleBookmark: bookmark.mutate,
    hideArticle: hide.mutate,
    isBookmarking: bookmark.isPending,
    isHiding: hide.isPending,
  };
}
