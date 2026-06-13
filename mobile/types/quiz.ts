export type AnswerKey = 'A' | 'B' | 'C' | 'D';

export interface QuizQuestion {
  id: number;
  question: string;
  options: Record<AnswerKey, string>;
  correct: AnswerKey;
  explanation: string;
}

export interface QuizGeneration {
  article_id: string;
  article_title: string;
  questions: QuizQuestion[];
}

export interface QuizAnswer {
  question_id: number;
  selected: AnswerKey;
}

export interface QuizAnswerResult {
  question_id: number;
  correct: boolean;
  feedback: string;
  explanation: string;
}

export interface QuizSubmission {
  score: number;
  correct_count: number;
  total_questions: number;
  results: QuizAnswerResult[];
}
