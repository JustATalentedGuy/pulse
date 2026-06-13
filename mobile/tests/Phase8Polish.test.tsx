import { fireEvent, render } from '@testing-library/react-native';
import { View } from 'react-native';

import { ArticleList } from '@/components/ArticleList';
import { NetworkBanner } from '@/components/NetworkBanner';
import { TrendingStrip } from '@/components/TrendingStrip';
import type { Article } from '@/types/article';


jest.mock('expo-network', () => ({
  useNetworkState: () => ({
    isConnected: false,
    isInternetReachable: false,
  }),
}));

jest.mock('@/components/ArticleCard', () => {
  const { Text: MockText } = require('react-native');

  return {
    ArticleCard: ({ article }: { article: Article }) => (
      <MockText>{article.title}</MockText>
    ),
  };
});

const cachedArticle = {
  id: 'cached',
  title: 'Cached offline article',
} as Article;

test('offline banner appears while cached articles remain scrollable', () => {
  const screen = render(
    <View>
      <NetworkBanner offlineOverride />
      <ArticleList
        articles={[cachedArticle]}
        emptyBody="No articles"
        emptyTitle="Empty"
        isLoading={false}
      />
    </View>,
  );

  expect(screen.getByText("You're offline. Showing saved articles.")).toBeTruthy();
  expect(screen.getByText('Cached offline article')).toBeTruthy();
  fireEvent.scroll(screen.getByTestId('article-list'), {
    nativeEvent: {
      contentOffset: { y: 100 },
      contentSize: { height: 1200, width: 390 },
      layoutMeasurement: { height: 800, width: 390 },
    },
  });
});

test('empty article list renders an illustration and helpful text', () => {
  const screen = render(
    <ArticleList
      articles={[]}
      emptyBody="Fresh stories will appear after the next ingestion run."
      emptyTitle="Your feed is ready for stories"
      isLoading={false}
    />,
  );

  expect(screen.getByTestId('empty-state-illustration')).toBeTruthy();
  expect(screen.getByText('Your feed is ready for stories')).toBeTruthy();
  expect(
    screen.getByText('Fresh stories will appear after the next ingestion run.'),
  ).toBeTruthy();
});

test('tapping a trend routes to search with the entity query', () => {
  const { router } = jest.requireMock('expo-router');
  const screen = render(
    <TrendingStrip
      trends={[
        {
          name: 'Claude 4',
          mention_count: 4,
          article_ids: ['a', 'b', 'c', 'd'],
          detected_at: '2026-06-13T00:00:00Z',
        },
      ]}
    />,
  );

  fireEvent.press(
    screen.getByRole('button', { name: 'Search trend Claude 4' }),
  );
  expect(router.push).toHaveBeenCalledWith({
    pathname: '/search',
    params: { q: 'Claude 4' },
  });
});
