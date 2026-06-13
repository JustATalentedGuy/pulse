import axios from 'axios';
import { useLocalSearchParams } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { QuizPanel } from '@/components/QuizPanel';
import { useGenerateQuiz, useSubmitQuiz } from '@/hooks/useQuiz';
import { colors, radius, spacing, typography } from '@/theme';
import type { AnswerKey, QuizAnswer } from '@/types/quiz';
import { lightHaptic } from '@/utils/haptics';

export default function QuizScreen() {
  const params = useLocalSearchParams<{
    articleId: string | string[];
  }>();
  const articleId = Array.isArray(params.articleId)
    ? params.articleId[0]
    : params.articleId;
  const generate = useGenerateQuiz(articleId ?? '');
  const submit = useSubmitQuiz(articleId ?? '');
  const startedAt = useRef(Date.now());
  const requested = useRef(false);
  const [questionIndex, setQuestionIndex] = useState(0);
  const [answers, setAnswers] = useState<QuizAnswer[]>([]);

  useEffect(() => {
    if (articleId && !requested.current) {
      requested.current = true;
      generate.mutate();
    }
  }, [articleId, generate]);

  const quiz = generate.data;
  const question = quiz?.questions[questionIndex];
  const selected =
    answers.find((answer) => answer.question_id === question?.id)?.selected ??
    null;

  const selectAnswer = (answer: AnswerKey) => {
    if (!question || selected) return;
    setAnswers((current) => [
      ...current,
      { question_id: question.id, selected: answer },
    ]);
  };

  const continueQuiz = () => {
    if (!quiz || !question || !selected) return;
    if (questionIndex < quiz.questions.length - 1) {
      setQuestionIndex((current) => current + 1);
      return;
    }
    submit.mutate({
      answers,
      durationSeconds: Math.max(
        1,
        Math.round((Date.now() - startedAt.current) / 1000),
      ),
    });
  };

  const error = generate.error ?? submit.error;
  const errorMessage =
    axios.isAxiosError(error) && typeof error.response?.data?.detail === 'string'
      ? error.response.data.detail
      : 'The quiz could not be loaded. Please try again.';

  if (generate.isPending || (!quiz && !error)) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator color={colors.accent} size="large" />
        <Text style={styles.loadingTitle}>Building your quiz</Text>
        <Text style={styles.loadingBody}>
          Pulse is turning the article into three concept questions.
        </Text>
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.centered}>
        <Text style={styles.errorTitle}>Quiz unavailable</Text>
        <Text style={styles.loadingBody}>{errorMessage}</Text>
        <Pressable
          onPress={() => {
            void lightHaptic();
            requested.current = true;
            generate.mutate();
          }}
          style={styles.retryButton}>
          <Text style={styles.retryText}>Try again</Text>
        </Pressable>
      </View>
    );
  }

  if (submit.data) {
    const percent = Math.round(submit.data.score * 100);
    return (
      <SafeAreaView edges={['bottom']} style={styles.safeArea}>
        <View style={styles.result}>
          <Text style={styles.resultEyebrow}>QUIZ COMPLETE</Text>
          <Text style={styles.score}>{percent}%</Text>
          <Text style={styles.resultTitle}>
            {submit.data.correct_count} of {submit.data.total_questions} correct
          </Text>
          <Text style={styles.loadingBody}>
            Your result is saved and now contributes to the article’s learning
            history.
          </Text>
        </View>
      </SafeAreaView>
    );
  }

  if (!quiz || !question) return null;

  return (
    <SafeAreaView edges={['bottom']} style={styles.safeArea}>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.articleTitle}>{quiz.article_title}</Text>
        <QuizPanel
          isLast={questionIndex === quiz.questions.length - 1}
          isSubmitting={submit.isPending}
          onContinue={continueQuiz}
          onSelect={selectAnswer}
          question={question}
          questionNumber={questionIndex + 1}
          selected={selected}
          totalQuestions={quiz.questions.length}
        />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: colors.background.primary,
  },
  content: {
    gap: spacing.xl,
    padding: spacing.xl,
    paddingBottom: spacing['3xl'],
  },
  articleTitle: {
    color: colors.text.tertiary,
    fontFamily: typography.fontFamily.medium,
    fontSize: typography.size.sm,
    lineHeight: 20,
  },
  centered: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.md,
    padding: spacing['2xl'],
    backgroundColor: colors.background.primary,
  },
  loadingTitle: {
    color: colors.text.primary,
    fontFamily: typography.fontFamily.semibold,
    fontSize: typography.size.md,
  },
  loadingBody: {
    color: colors.text.secondary,
    fontFamily: typography.fontFamily.regular,
    fontSize: typography.size.sm,
    lineHeight: 21,
    textAlign: 'center',
  },
  errorTitle: {
    color: colors.error,
    fontFamily: typography.fontFamily.semibold,
    fontSize: typography.size.md,
  },
  retryButton: {
    marginTop: spacing.sm,
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
  result: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.md,
    padding: spacing['2xl'],
  },
  resultEyebrow: {
    color: colors.accent,
    fontFamily: typography.fontFamily.semibold,
    fontSize: typography.size.xs,
    letterSpacing: 1.2,
  },
  score: {
    color: colors.text.primary,
    fontFamily: typography.fontFamily.bold,
    fontSize: 64,
  },
  resultTitle: {
    color: colors.text.primary,
    fontFamily: typography.fontFamily.semibold,
    fontSize: typography.size.lg,
  },
});
