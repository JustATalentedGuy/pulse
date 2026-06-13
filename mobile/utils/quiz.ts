import type { AnswerKey, QuizQuestion } from '@/types/quiz';

export function localQuizFeedback(
  question: QuizQuestion,
  selected: AnswerKey,
) {
  if (selected === question.correct) {
    return `Good reasoning. ${question.explanation}`;
  }
  return `What distinction makes option ${question.correct} fit better than option ${selected}? ${question.explanation}`;
}
