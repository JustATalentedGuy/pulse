import { fireEvent, render } from '@testing-library/react-native';

import { CategoryFilterBar } from '@/components/CategoryFilterBar';

test('active category clears when tapped again', () => {
  const onSelect = jest.fn();
  const screen = render(
    <CategoryFilterBar onSelect={onSelect} selected="models" />,
  );

  const chip = screen.getByRole('button', { name: 'models' });
  expect(chip.props.accessibilityState).toEqual({ selected: true });
  fireEvent.press(chip);
  expect(onSelect).toHaveBeenCalledWith(null);
});
