import { render } from '@testing-library/react-native';

import { ARTICLE_CARD_MIN_HEIGHT } from '@/components/constants';
import { SkeletonCard } from '@/components/SkeletonCard';

test('skeleton reserves the same minimum height as an article card', () => {
  const screen = render(<SkeletonCard />);
  expect(screen.getByTestId('skeleton-card')).toHaveStyle({
    minHeight: ARTICLE_CARD_MIN_HEIGHT,
  });
});
