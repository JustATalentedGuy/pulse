import { Pressable, ScrollView, StyleSheet, Text } from 'react-native';

import { colors, radius, spacing, typography } from '@/theme';
import type { CategoryKey } from '@/types/article';
import { lightHaptic } from '@/utils/haptics';

const categories: CategoryKey[] = [
  'models',
  'research',
  'tools',
  'cloud',
  'industry',
  'other',
];

interface CategoryFilterBarProps {
  selected: CategoryKey | null;
  onSelect: (category: CategoryKey | null) => void;
}

export function CategoryFilterBar({
  selected,
  onSelect,
}: CategoryFilterBarProps) {
  return (
    <ScrollView
      contentContainerStyle={styles.content}
      horizontal
      showsHorizontalScrollIndicator={false}>
      {categories.map((category) => {
        const active = selected === category;
        return (
          <Pressable
            accessibilityRole="button"
            accessibilityState={{ selected: active }}
            key={category}
            onPress={() => {
              void lightHaptic();
              onSelect(active ? null : category);
            }}
            style={[styles.chip, active && styles.activeChip]}>
            <Text style={[styles.label, active && styles.activeLabel]}>
              {category}
            </Text>
          </Pressable>
        );
      })}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: {
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.lg,
  },
  chip: {
    paddingHorizontal: 14,
    paddingVertical: spacing.sm,
    borderRadius: radius.full,
    backgroundColor: colors.background.tertiary,
  },
  activeChip: {
    backgroundColor: colors.accent,
  },
  label: {
    color: colors.text.secondary,
    fontFamily: typography.fontFamily.medium,
    fontSize: typography.size.sm,
    textTransform: 'capitalize',
  },
  activeLabel: {
    color: colors.text.primary,
  },
});
