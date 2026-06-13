import { SymbolView } from 'expo-symbols';
import { router } from 'expo-router';
import { useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useAsk } from '@/hooks/useAsk';
import { colors, radius, spacing, typography } from '@/theme';
import type { ConversationMessage } from '@/types/phase8';
import { lightHaptic } from '@/utils/haptics';

export default function AskScreen() {
  const ask = useAsk();
  const [question, setQuestion] = useState('');
  const [history, setHistory] = useState<ConversationMessage[]>([]);
  const normalized = question.trim();

  const submit = () => {
    if (normalized.length < 2 || ask.isPending) return;
    void lightHaptic();
    const currentQuestion = normalized;
    ask.mutate(
      {
        question: currentQuestion,
        conversationHistory: history,
      },
      {
        onSuccess: (response) => {
          setHistory((current) => [
            ...current,
            { role: 'user', content: currentQuestion },
            { role: 'assistant', content: response.answer },
          ].slice(-6) as ConversationMessage[]);
          setQuestion('');
        },
      },
    );
  };

  return (
    <SafeAreaView edges={['top']} style={styles.safeArea}>
      <ScrollView
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled">
        <View style={styles.header}>
          <Text style={styles.title}>Ask Pulse</Text>
          <Text style={styles.subtitle}>
            Answers grounded in your saved intelligence corpus
          </Text>
        </View>

        {!ask.data && !ask.isPending && (
          <View style={styles.empty}>
            <SymbolView
              name={{
                ios: 'sparkles',
                android: 'auto_awesome',
                web: 'auto_awesome',
              }}
              tintColor={colors.accent}
              size={40}
            />
            <Text style={styles.emptyTitle}>Ask across every article</Text>
            <Text style={styles.emptyBody}>
              Try “What approaches are emerging for reliable AI agents?”
            </Text>
          </View>
        )}

        {ask.isPending && (
          <View style={styles.loading}>
            <ActivityIndicator color={colors.accent} />
            <Text style={styles.emptyBody}>Searching the corpus...</Text>
          </View>
        )}

        {ask.isError && (
          <View style={styles.errorCard}>
            <Text style={styles.errorTitle}>Ask mode is unavailable</Text>
            <Text style={styles.emptyBody}>
              Check the connection, then retry your question.
            </Text>
            <Pressable onPress={submit} style={styles.retryButton}>
              <Text style={styles.buttonText}>Retry</Text>
            </Pressable>
          </View>
        )}

        {ask.data && (
          <View style={styles.answerCard}>
            <Text style={styles.answer}>{ask.data.answer}</Text>
            {ask.data.sources.length > 0 && (
              <View style={styles.sources}>
                <Text style={styles.sourceLabel}>SOURCES</Text>
                {ask.data.sources.map((source) => (
                  <Pressable
                    accessibilityRole="button"
                    key={source.id}
                    onPress={() => {
                      void lightHaptic();
                      router.push({
                        pathname: '/article/[id]',
                        params: { id: source.id },
                      });
                    }}
                    style={styles.source}>
                    <Text numberOfLines={2} style={styles.sourceTitle}>
                      {source.title}
                    </Text>
                    <Text style={styles.similarity}>
                      {Math.round(source.similarity * 100)}% match
                    </Text>
                  </Pressable>
                ))}
              </View>
            )}
          </View>
        )}
      </ScrollView>

      <View style={styles.composer}>
        <TextInput
          accessibilityLabel="Ask Pulse"
          multiline
          onChangeText={setQuestion}
          placeholder="Ask about models, tools, research..."
          placeholderTextColor={colors.text.secondary}
          style={styles.input}
          value={question}
        />
        <Pressable
          accessibilityLabel="Send question"
          accessibilityRole="button"
          disabled={normalized.length < 2 || ask.isPending}
          onPress={submit}
          style={[
            styles.sendButton,
            (normalized.length < 2 || ask.isPending) && styles.disabled,
          ]}>
          <SymbolView
            name={{
              ios: 'arrow.up',
              android: 'arrow_upward',
              web: 'arrow_upward',
            }}
            tintColor={colors.text.primary}
            size={22}
          />
        </Pressable>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: colors.background.primary,
  },
  content: {
    flexGrow: 1,
    gap: spacing.xl,
    padding: spacing.lg,
    paddingBottom: 120,
  },
  header: {
    gap: spacing.xs,
  },
  title: {
    color: colors.text.primary,
    fontFamily: typography.fontFamily.bold,
    fontSize: typography.size['2xl'],
  },
  subtitle: {
    color: colors.text.secondary,
    fontFamily: typography.fontFamily.regular,
    fontSize: typography.size.sm,
  },
  empty: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.md,
    minHeight: 360,
  },
  emptyTitle: {
    color: colors.text.primary,
    fontFamily: typography.fontFamily.semibold,
    fontSize: typography.size.md,
  },
  emptyBody: {
    color: colors.text.secondary,
    fontFamily: typography.fontFamily.regular,
    fontSize: typography.size.sm,
    lineHeight: 21,
    textAlign: 'center',
  },
  loading: {
    alignItems: 'center',
    gap: spacing.md,
    paddingTop: 100,
  },
  errorCard: {
    alignItems: 'center',
    gap: spacing.md,
    padding: spacing.xl,
    borderRadius: radius.lg,
    backgroundColor: colors.background.secondary,
  },
  errorTitle: {
    color: colors.error,
    fontFamily: typography.fontFamily.semibold,
    fontSize: typography.size.md,
  },
  retryButton: {
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.md,
    borderRadius: radius.lg,
    backgroundColor: colors.accent,
  },
  buttonText: {
    color: colors.text.primary,
    fontFamily: typography.fontFamily.semibold,
    fontSize: typography.size.sm,
  },
  answerCard: {
    gap: spacing.xl,
    padding: spacing.xl,
    borderWidth: 1,
    borderColor: colors.border.default,
    borderRadius: radius.xl,
    backgroundColor: colors.background.secondary,
  },
  answer: {
    color: colors.text.primary,
    fontFamily: typography.fontFamily.regular,
    fontSize: typography.size.base,
    lineHeight: 25,
  },
  sources: {
    gap: spacing.sm,
  },
  sourceLabel: {
    color: colors.text.secondary,
    fontFamily: typography.fontFamily.semibold,
    fontSize: typography.size.xs,
    letterSpacing: 1,
  },
  source: {
    gap: spacing.xs,
    padding: spacing.md,
    borderRadius: radius.md,
    backgroundColor: colors.background.tertiary,
  },
  sourceTitle: {
    color: colors.text.primary,
    fontFamily: typography.fontFamily.medium,
    fontSize: typography.size.sm,
  },
  similarity: {
    color: '#C4B5FD',
    fontFamily: typography.fontFamily.mono,
    fontSize: typography.size.xs,
  },
  composer: {
    position: 'absolute',
    left: spacing.lg,
    right: spacing.lg,
    bottom: 76,
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: spacing.sm,
    padding: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border.strong,
    borderRadius: radius.xl,
    backgroundColor: colors.background.tertiary,
  },
  input: {
    flex: 1,
    maxHeight: 100,
    minHeight: 44,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.sm,
    color: colors.text.primary,
    fontFamily: typography.fontFamily.regular,
    fontSize: typography.size.base,
  },
  sendButton: {
    width: 44,
    height: 44,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radius.full,
    backgroundColor: colors.accent,
  },
  disabled: {
    opacity: 0.4,
  },
});
