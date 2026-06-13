import { fireEvent, render } from '@testing-library/react-native';

import { SearchModeSelector } from '@/components/SearchModeSelector';


test('semantic mode can be selected', () => {
  const onSelect = jest.fn();
  const screen = render(
    <SearchModeSelector onSelect={onSelect} selected="hybrid" />,
  );

  fireEvent.press(screen.getByRole('button', { name: 'semantic' }));
  expect(onSelect).toHaveBeenCalledWith('semantic');
});
