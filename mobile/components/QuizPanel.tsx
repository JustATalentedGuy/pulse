import { Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, radius, spacing, typography } from '@/theme';
import type { AnswerKey, QuizQuestion } from '@/types/quiz';
import { localQuizFeedback } from '@/utils/quiz';
import { lightHaptic } from '@/utils/haptics';

const ANSWER_KEYS: AnswerKey[] = ['A', 'B', 'C', 'D'];

interface QuizPanelProps {
  question: QuizQuestion;
  questionNumber: number;
  totalQuestions: number;
  selected: AnswerKey | null;
  onSelect: (answer: AnswerKey) => void;
  onContinue: () => void;
  isLast: boolean;
  isSubmitting?: boolean;
}

export function QuizPanel({
  question,
  questionNumber,
  totalQuestions,
  selected,
  onSelect,
  onContinue,
  isLast,
  isSubmitting = false,
}: QuizPanelProps) {
  return (
    <View style={styles.panel}>
      <Text style={styles.progress}>
        QUESTION {questionNumber} OF {totalQuestions}
      </Text>
      <Text style={styles.question}>{question.question}</Text>
      <View style={styles.options}>
        {ANSWER_KEYS.map((key) => {
          const isSelected = selected === key;
          const isCorrect = selected !== null && question.correct === key;
          return (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={`${key}: ${question.options[key]}`}
              disabled={selected !== null}
              key={key}
              onPress={() => {
                void lightHaptic();
                onSelect(key);
              }}
              style={[
                styles.option,
                isSelected && styles.selectedOption,
                isCorrect && styles.correctOption,
              ]}>
              <Text
                style={[
                  styles.optionKey,
                  (isSelected || isCorrect) && styles.activeOptionText,
                ]}>
                {key}
              </Text>
              <Text
                style={[
                  styles.optionText,
                  (isSelected || isCorrect) && styles.activeOptionText,
                ]}>
                {question.options[key]}
              </Text>
            </Pressable>
          );
        })}
      </View>
      {selected && (
        <View
          style={[
            styles.feedback,
            selected === question.correct
              ? styles.correctFeedback
              : styles.incorrectFeedback,
          ]}>
          <Text style={styles.feedbackTitle}>
            {selected === question.correct ? 'Strong answer' : 'Think it through'}
          </Text>
          <Text style={styles.feedbackText}>
            {localQuizFeedback(question, selected)}
          </Text>
        </View>
      )}
      <Pressable
        accessibilityRole="button"
        disabled={!selected || isSubmitting}
        onPress={() => {
          void lightHaptic();
          onContinue();
        }}
        style={[
          styles.continueButton,
          (!selected || isSubmitting) && styles.disabledButton,
        ]}>
        <Text style={styles.continueText}>
          {isSubmitting ? 'Saving score...' : isLast ? 'Finish quiz' : 'Next question'}
        </Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  panel: {
    gap: spacing.xl,
  },
  progress: {
    color: colors.accent,
    fontFamily: typography.fontFamily.semibold,
    fontSize: typography.size.xs,
    letterSpacing: 1,
  },
  question: {
    color: colors.text.primary,
    fontFamily: typography.fontFamily.semibold,
    fontSize: typography.size.lg,
    lineHeight: 28,
  },
  options: {
    gap: spacing.md,
  },
  option: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: colors.border.default,
    borderRadius: radius.lg,
    backgroundColor: colors.background.secondary,
  },
  selectedOption: {
    borderColor: colors.warning,
    backgroundColor: '#2A1D0D',
  },
  correctOption: {
    borderColor: colors.success,
    backgroundColor: '#0D241B',
  },
  optionKey: {
    color: colors.text.tertiary,
    fontFamily: typography.fontFamily.bold,
    fontSize: typography.size.sm,
  },
  optionText: {
    flex: 1,
    color: colors.text.secondary,
    fontFamily: typography.fontFamily.regular,
    fontSize: typography.size.sm,
    lineHeight: 20,
  },
  activeOptionText: {
    color: colors.text.primary,
  },
  feedback: {
    gap: spacing.sm,
    padding: spacing.lg,
    borderRadius: radius.lg,
    borderWidth: 1,
  },
  correctFeedback: {
    borderColor: colors.success,
    backgroundColor: '#0D241B',
  },
  incorrectFeedback: {
    borderColor: colors.warning,
    backgroundColor: '#2A1D0D',
  },
  feedbackTitle: {
    color: colors.text.primary,
    fontFamily: typography.fontFamily.semibold,
    fontSize: typography.size.sm,
  },
  feedbackText: {
    color: colors.text.secondary,
    fontFamily: typography.fontFamily.regular,
    fontSize: typography.size.sm,
    lineHeight: 21,
  },
  continueButton: {
    alignItems: 'center',
    padding: spacing.lg,
    borderRadius: radius.lg,
    backgroundColor: colors.accent,
  },
  disabledButton: {
    opacity: 0.4,
  },
  continueText: {
    color: colors.text.primary,
    fontFamily: typography.fontFamily.semibold,
    fontSize: typography.size.base,
  },
});
