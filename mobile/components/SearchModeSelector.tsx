import { Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, radius, spacing, typography } from '@/theme';
import type { SearchMode } from '@/types/article';
import { lightHaptic } from '@/utils/haptics';


const modes: SearchMode[] = ['hybrid', 'semantic', 'fts'];


interface SearchModeSelectorProps {
  selected: SearchMode;
  onSelect: (mode: SearchMode) => void;
}


export function SearchModeSelector({
  selected,
  onSelect,
}: SearchModeSelectorProps) {
  return (
    <View style={styles.container}>
      {modes.map((mode) => {
        const active = mode === selected;
        return (
          <Pressable
            accessibilityRole="button"
            accessibilityState={{ selected: active }}
            key={mode}
            onPress={() => {
              void lightHaptic();
              onSelect(mode);
            }}
            style={[styles.option, active && styles.activeOption]}>
            <Text style={[styles.label, active && styles.activeLabel]}>
              {mode === 'fts' ? 'Exact' : mode}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}


const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    gap: spacing.xs,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    padding: spacing.xs,
    borderRadius: radius.full,
    backgroundColor: colors.background.secondary,
  },
  option: {
    flex: 1,
    alignItems: 'center',
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.sm,
    borderRadius: radius.full,
  },
  activeOption: {
    backgroundColor: colors.accentSoft,
  },
  label: {
    color: colors.text.tertiary,
    fontFamily: typography.fontFamily.medium,
    fontSize: typography.size.xs,
    textTransform: 'capitalize',
  },
  activeLabel: {
    color: '#C4B5FD',
  },
});
