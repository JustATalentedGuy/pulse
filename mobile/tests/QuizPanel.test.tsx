import { fireEvent, render } from '@testing-library/react-native';

import { QuizPanel } from '@/components/QuizPanel';
import type { QuizQuestion } from '@/types/quiz';


const question: QuizQuestion = {
  id: 1,
  question: 'Why use reciprocal rank fusion?',
  options: {
    A: 'To merge rankings',
    B: 'To delete articles',
    C: 'To create embeddings',
    D: 'To schedule jobs',
  },
  correct: 'A',
  explanation: 'It combines ranked lists without matching raw score scales.',
};

test('selecting an answer reveals Socratic feedback', () => {
  const onSelect = jest.fn();
  const screen = render(
    <QuizPanel
      isLast={false}
      onContinue={jest.fn()}
      onSelect={onSelect}
      question={question}
      questionNumber={1}
      selected="B"
      totalQuestions={3}
    />,
  );

  expect(screen.getByText('Think it through')).toBeTruthy();
  expect(screen.getByText(/What distinction makes option A fit better/)).toBeTruthy();
  fireEvent.press(screen.getByRole('button', { name: 'Next question' }));
});
