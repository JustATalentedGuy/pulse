import { SymbolView } from 'expo-symbols';
import * as WebBrowser from 'expo-web-browser';
import { router, useLocalSearchParams } from 'expo-router';
import { useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import Animated, {
  useAnimatedScrollHandler,
  useAnimatedStyle,
  useSharedValue,
} from 'react-native-reanimated';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useArticle } from '@/hooks/useArticle';
import { useArticleActions } from '@/hooks/useArticleActions';
import { useReadTimer } from '@/hooks/useReadTimer';
import { colors, radius, spacing, typography } from '@/theme';
import type { Article, CategoryKey } from '@/types/article';
import { lightHaptic } from '@/utils/haptics';

function ArticleDetail({ article }: { article: Article }) {
  useReadTimer(article.id);
  const progress = useSharedValue(0);
  const [contentHeight, setContentHeight] = useState(0);
  const [viewportHeight, setViewportHeight] = useState(0);
  const showProgress =
    viewportHeight > 0 && contentHeight > viewportHeight * 2;
  const category = (article.category ?? 'other') as CategoryKey;
  const categoryColor = colors.category[category];
  const { toggleBookmark, isBookmarking } = useArticleActions(article);
  const entities = useMemo(
    () =>
      Object.entries(article.entities).flatMap(([type, values]) =>
        (values as string[]).map((value: string) => ({ type, value })),
      ),
    [article.entities],
  );
  const scrollHandler = useAnimatedScrollHandler({
    onScroll: (event) => {
      const scrollable =
        event.contentSize.height - event.layoutMeasurement.height;
      progress.value =
        scrollable <= 0
          ? 0
          : Math.min(1, event.contentOffset.y / scrollable);
    },
  });
  const progressStyle = useAnimatedStyle(() => ({
    width: `${progress.value * 100}%`,
  }));

  return (
    <SafeAreaView edges={['bottom']} style={styles.safeArea}>
      {showProgress ? (
        <Animated.View
          style={[
            styles.progress,
            progressStyle,
            { backgroundColor: categoryColor.dot },
          ]}
        />
      ) : null}
      <Animated.ScrollView
        contentContainerStyle={styles.content}
        onContentSizeChange={(_, height) => setContentHeight(height)}
        onLayout={(event) =>
          setViewportHeight(event.nativeEvent.layout.height)
        }
        onScroll={scrollHandler}
        scrollEventThrottle={16}>
        <View
          style={[styles.hero, { borderTopColor: categoryColor.dot }]}>
          <View style={styles.metaRow}>
            <Text style={styles.source}>{article.source.toUpperCase()}</Text>
            <Pressable
              accessibilityLabel={
                article.bookmarked ? 'Remove bookmark' : 'Bookmark article'
              }
              disabled={isBookmarking}
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
                  article.bookmarked ? colors.accent : colors.text.secondary
                }
                size={26}
              />
            </Pressable>
          </View>
          <Text style={styles.title}>{article.title}</Text>
          <Text style={[styles.category, { color: categoryColor.text }]}>
            {category}
          </Text>
        </View>
        {entities.length > 0 && (
          <ScrollView
            contentContainerStyle={styles.entities}
            horizontal
            showsHorizontalScrollIndicator={false}>
            {entities.map((entity) => (
              <View
                key={`${entity.type}-${entity.value}`}
                style={styles.entity}>
                <Text style={styles.entityType}>{entity.type}</Text>
                <Text style={styles.entityValue}>{entity.value}</Text>
              </View>
            ))}
          </ScrollView>
        )}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Summary</Text>
          <Text style={styles.summary}>
            {article.summary ??
              'This article is waiting for enrichment. Open the source to read it now.'}
          </Text>
        </View>
        {article.keywords.length > 0 && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Keywords</Text>
            <View style={styles.keywordRow}>
              {article.keywords.map((keyword) => (
                <View key={keyword} style={styles.keyword}>
                  <Text style={styles.keywordText}>{keyword}</Text>
                </View>
              ))}
            </View>
          </View>
        )}
        {article.summary && article.category && (
          <Pressable
            accessibilityRole="button"
            onPress={() =>
              void lightHaptic().then(() =>
                router.push({
                  pathname: '/quiz/[articleId]',
                  params: { articleId: article.id },
                }),
              )
            }
            style={styles.quizButton}>
            <SymbolView
              name={{
                ios: 'brain.head.profile',
                android: 'psychology',
                web: 'psychology',
              }}
              tintColor={colors.accent}
              size={22}
            />
            <View style={styles.quizCopy}>
              <Text style={styles.quizTitle}>
                {article.quiz_attempted ? 'Retake quiz' : 'Test yourself'}
              </Text>
              <Text style={styles.quizBody}>
                Three concept questions with guided feedback
              </Text>
            </View>
          </Pressable>
        )}
        <Pressable
          accessibilityRole="link"
          onPress={() => {
            void lightHaptic();
            void WebBrowser.openBrowserAsync(article.url);
          }}
          style={styles.link}>
          <Text style={styles.linkText}>Read full article</Text>
          <SymbolView
            name={{
              ios: 'arrow.up.right',
              android: 'open_in_new',
              web: 'open_in_new',
            }}
            tintColor={colors.text.primary}
            size={20}
          />
        </Pressable>
      </Animated.ScrollView>
    </SafeAreaView>
  );
}

export default function ArticleDetailScreen() {
  const params = useLocalSearchParams<{ id: string | string[] }>();
  const articleId = Array.isArray(params.id) ? params.id[0] : params.id;
  const article = useArticle(articleId ?? '');

  if (article.isLoading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator color={colors.accent} size="large" />
      </View>
    );
  }
  if (!article.data) {
    return (
      <View style={styles.centered}>
        <Text style={styles.error}>Article unavailable.</Text>
        <Pressable
          accessibilityRole="button"
          onPress={() => void article.refetch()}
          style={styles.retryButton}>
          <Text style={styles.retryText}>Retry</Text>
        </Pressable>
      </View>
    );
  }
  return <ArticleDetail article={article.data} />;
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: colors.background.primary,
  },
  progress: {
    position: 'absolute',
    top: 0,
    left: 0,
    zIndex: 10,
    height: 2,
  },
  content: {
    gap: spacing.xl,
    paddingBottom: spacing['3xl'],
  },
  hero: {
    gap: spacing.md,
    padding: spacing.xl,
    borderTopWidth: 4,
    backgroundColor: colors.background.secondary,
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
    letterSpacing: 0.8,
  },
  title: {
    color: colors.text.primary,
    fontFamily: typography.fontFamily.bold,
    fontSize: typography.size.xl,
    lineHeight: 32,
  },
  category: {
    fontFamily: typography.fontFamily.medium,
    fontSize: typography.size.sm,
    textTransform: 'capitalize',
  },
  entities: {
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
  },
  entity: {
    gap: 2,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
    backgroundColor: colors.background.tertiary,
  },
  entityType: {
    color: colors.text.tertiary,
    fontFamily: typography.fontFamily.medium,
    fontSize: 9,
    textTransform: 'uppercase',
  },
  entityValue: {
    color: colors.text.primary,
    fontFamily: typography.fontFamily.mono,
    fontSize: typography.size.xs,
  },
  section: {
    gap: spacing.md,
    paddingHorizontal: spacing.xl,
  },
  sectionTitle: {
    color: colors.text.primary,
    fontFamily: typography.fontFamily.semibold,
    fontSize: typography.size.md,
  },
  summary: {
    color: colors.text.secondary,
    fontFamily: typography.fontFamily.regular,
    fontSize: typography.size.base,
    lineHeight: 25,
  },
  keywordRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
  },
  keyword: {
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: radius.full,
    backgroundColor: colors.background.tertiary,
  },
  keywordText: {
    color: colors.text.secondary,
    fontFamily: typography.fontFamily.medium,
    fontSize: typography.size.xs,
  },
  link: {
    marginHorizontal: spacing.xl,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    padding: spacing.lg,
    borderRadius: radius.lg,
    backgroundColor: colors.accent,
  },
  quizButton: {
    marginHorizontal: spacing.xl,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: colors.accent,
    borderRadius: radius.lg,
    backgroundColor: colors.accentSoft,
  },
  quizCopy: {
    flex: 1,
    gap: 2,
  },
  quizTitle: {
    color: colors.text.primary,
    fontFamily: typography.fontFamily.semibold,
    fontSize: typography.size.base,
  },
  quizBody: {
    color: colors.text.secondary,
    fontFamily: typography.fontFamily.regular,
    fontSize: typography.size.xs,
  },
  linkText: {
    color: colors.text.primary,
    fontFamily: typography.fontFamily.semibold,
    fontSize: typography.size.base,
  },
  centered: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.background.primary,
  },
  error: {
    color: colors.error,
    fontFamily: typography.fontFamily.medium,
    fontSize: typography.size.base,
  },
  retryButton: {
    marginTop: spacing.md,
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.md,
    borderRadius: radius.lg,
    backgroundColor: colors.accent,
  },
  retryText: {
    color: colors.text.primary,
    fontFamily: typography.fontFamily.semibold,
    fontSize: typography.size.sm,
  },
});
