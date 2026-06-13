import { formatDistanceToNow } from 'date-fns';
import { SymbolView } from 'expo-symbols';
import { router } from 'expo-router';
import { useEffect } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import Animated, {
  useAnimatedStyle,
  useSharedValue,
  withDelay,
  withSpring,
  withTiming,
} from 'react-native-reanimated';

import { useArticleActions } from '@/hooks/useArticleActions';
import { ARTICLE_CARD_MIN_HEIGHT } from '@/components/constants';
import { SourceAvatar } from '@/components/SourceAvatar';
import {
  animation,
  colors,
  radius,
  spacing,
  typography,
} from '@/theme';
import type { Article, CategoryKey } from '@/types/article';
import { articleStaggerDelay } from '@/utils/articles';
import { lightHaptic } from '@/utils/haptics';

interface ArticleCardProps {
  article: Article;
  index?: number;
  compact?: boolean;
}

export function ArticleCard({
  article,
  index = 0,
  compact = false,
}: ArticleCardProps) {
  const opacity = useSharedValue(0);
  const translateY = useSharedValue(20);
  const scale = useSharedValue(1);
  const category = (article.category ?? 'other') as CategoryKey;
  const categoryColor = colors.category[category];
  const { toggleBookmark, hideArticle, isBookmarking, isHiding } =
    useArticleActions(article);

  useEffect(() => {
    const delay = articleStaggerDelay(index);
    opacity.value = withDelay(delay, withTiming(1, { duration: 250 }));
    translateY.value = withDelay(
      delay,
      withSpring(0, animation.spring),
    );
  }, [index, opacity, translateY]);

  const animatedStyle = useAnimatedStyle(() => ({
    opacity: opacity.value,
    transform: [
      { translateY: translateY.value },
      { scale: scale.value },
    ],
  }));
  const publishedAt = article.published_at ?? article.ingested_at;
  const isOld =
    Date.now() - new Date(publishedAt).getTime() > 7 * 24 * 60 * 60 * 1000;
  const importance = article.importance ?? 1;

  return (
    <Animated.View
      testID={`article-card-${article.id}`}
      style={[
        styles.wrapper,
        styles.card,
        compact && styles.compactCard,
        { borderLeftColor: categoryColor.dot },
        animatedStyle,
        isOld && styles.old,
      ]}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`Open ${article.title}`}
        disabled={isHiding}
        onPress={() =>
          void lightHaptic().then(() =>
            router.push({
              pathname: '/article/[id]',
              params: { id: article.id },
            }),
          )
        }
        onPressIn={() => {
          scale.value = withSpring(0.985, animation.spring);
        }}
        onPressOut={() => {
          scale.value = withSpring(1, animation.spring);
        }}
        style={styles.mainPressTarget}>
        <View style={styles.metaRow}>
          <View style={styles.sourceRow}>
            <SourceAvatar
              domain={article.source_domain}
              source={article.source}
            />
            <Text style={styles.source}>{article.source.toUpperCase()}</Text>
          </View>
          <View style={[styles.category, { backgroundColor: categoryColor.bg }]}>
            <Text style={[styles.categoryText, { color: categoryColor.text }]}>
              {category}
            </Text>
          </View>
        </View>
        <Text numberOfLines={2} style={styles.title}>
          {article.title}
        </Text>
        {!compact && (
          <Text numberOfLines={3} style={styles.summary}>
            {article.summary ??
              'Enrichment pending. Open the source for the full article.'}
          </Text>
        )}
        <View style={styles.footer}>
          <View
            accessibilityLabel={`Importance ${importance} of 5`}
            style={styles.importance}>
            {Array.from({ length: 5 }, (_, dot) => (
              <View
                key={dot}
                style={[
                  styles.importanceDot,
                  {
                    backgroundColor:
                      dot < importance
                        ? colors.importance[
                            importance as keyof typeof colors.importance
                          ]
                        : colors.border.strong,
                  },
                ]}
              />
            ))}
          </View>
          <Text style={styles.time}>
            {formatDistanceToNow(new Date(publishedAt), { addSuffix: true })}
          </Text>
        </View>
      </Pressable>
      <View style={styles.actions}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={
            article.bookmarked ? 'Remove bookmark' : 'Bookmark article'
          }
          disabled={isBookmarking}
          hitSlop={10}
          onPress={() => {
            void lightHaptic();
            toggleBookmark();
          }}>
          <SymbolView
            name={{
              ios: article.bookmarked ? 'bookmark.fill' : 'bookmark',
              android: article.bookmarked ? 'bookmark' : 'bookmark_border',
              web: article.bookmarked ? 'bookmark' : 'bookmark_border',
            }}
            tintColor={
              article.bookmarked ? colors.accent : colors.text.tertiary
            }
            size={20}
          />
        </Pressable>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Hide article"
          disabled={isHiding}
          hitSlop={10}
          onPress={() => {
            void lightHaptic();
            hideArticle();
          }}>
          <SymbolView
            name={{
              ios: 'eye.slash',
              android: 'visibility_off',
              web: 'visibility_off',
            }}
            tintColor={colors.text.tertiary}
            size={20}
          />
        </Pressable>
      </View>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  wrapper: {
    minHeight: ARTICLE_CARD_MIN_HEIGHT,
  },
  old: {
    opacity: 0.62,
  },
  card: {
    minHeight: ARTICLE_CARD_MIN_HEIGHT,
    gap: spacing.sm,
    paddingHorizontal: 14,
    paddingVertical: 12,
    backgroundColor: colors.background.secondary,
    borderColor: colors.border.subtle,
    borderWidth: 1,
    borderLeftWidth: 3,
    borderRadius: radius.lg,
  },
  mainPressTarget: {
    flex: 1,
    gap: spacing.sm,
  },
  compactCard: {
    minHeight: 126,
  },
  metaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  source: {
    color: colors.text.tertiary,
    fontFamily: typography.fontFamily.semibold,
    fontSize: typography.size.xs,
    letterSpacing: 0.6,
  },
  sourceRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  category: {
    borderRadius: radius.full,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
  },
  categoryText: {
    fontFamily: typography.fontFamily.medium,
    fontSize: typography.size.xs,
    textTransform: 'capitalize',
  },
  title: {
    color: colors.text.primary,
    fontFamily: typography.fontFamily.semibold,
    fontSize: typography.size.base,
    lineHeight: 21,
  },
  summary: {
    color: colors.text.secondary,
    fontFamily: typography.fontFamily.regular,
    fontSize: typography.size.sm,
    lineHeight: 20,
  },
  footer: {
    marginTop: 'auto',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  importance: {
    flexDirection: 'row',
    gap: 4,
  },
  importanceDot: {
    width: 6,
    height: 6,
    borderRadius: radius.full,
  },
  time: {
    color: colors.text.tertiary,
    fontFamily: typography.fontFamily.regular,
    fontSize: typography.size.xs,
  },
  actions: {
    position: 'absolute',
    right: 12,
    bottom: 36,
    flexDirection: 'row',
    gap: spacing.md,
  },
});
