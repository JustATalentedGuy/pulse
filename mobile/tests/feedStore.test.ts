import { useFeedStore } from '@/store/feedStore';

afterEach(() => {
  useFeedStore.setState({
    selectedCategory: null,
    minImportance: 1,
    activeReadTimers: {},
  });
  jest.restoreAllMocks();
});

test('category can be selected and cleared', () => {
  useFeedStore.getState().setCategory('models');
  expect(useFeedStore.getState().selectedCategory).toBe('models');
  useFeedStore.getState().setCategory(null);
  expect(useFeedStore.getState().selectedCategory).toBeNull();
});

test('read timer returns the elapsed whole seconds', () => {
  const now = jest.spyOn(Date, 'now');
  now.mockReturnValueOnce(1_000);
  useFeedStore.getState().startReadTimer('article-1');
  now.mockReturnValueOnce(11_100);
  expect(useFeedStore.getState().stopReadTimer('article-1')).toBe(10);
  expect(useFeedStore.getState().activeReadTimers).toEqual({});
});
