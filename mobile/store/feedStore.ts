import { create } from 'zustand';

import type { CategoryKey } from '@/types/article';

interface FeedStore {
  selectedCategory: CategoryKey | null;
  minImportance: number;
  activeReadTimers: Record<string, number>;
  setCategory: (category: CategoryKey | null) => void;
  setMinImportance: (importance: number) => void;
  startReadTimer: (id: string) => void;
  stopReadTimer: (id: string) => number;
}

export const useFeedStore = create<FeedStore>((set, get) => ({
  selectedCategory: null,
  minImportance: 1,
  activeReadTimers: {},
  setCategory: (selectedCategory) => set({ selectedCategory }),
  setMinImportance: (minImportance) => set({ minImportance }),
  startReadTimer: (id) =>
    set((state) => ({
      activeReadTimers: {
        ...state.activeReadTimers,
        [id]: Date.now(),
      },
    })),
  stopReadTimer: (id) => {
    const startedAt = get().activeReadTimers[id];
    if (!startedAt) return 0;
    set((state) => {
      const activeReadTimers = { ...state.activeReadTimers };
      delete activeReadTimers[id];
      return { activeReadTimers };
    });
    return Math.max(0, Math.round((Date.now() - startedAt) / 1000));
  },
}));
