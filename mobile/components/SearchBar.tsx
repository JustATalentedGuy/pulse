import { SymbolView } from 'expo-symbols';
import { StyleSheet, TextInput, View } from 'react-native';

import { colors, radius, spacing, typography } from '@/theme';

interface SearchBarProps {
  value: string;
  onChangeText: (value: string) => void;
}

export function SearchBar({ value, onChangeText }: SearchBarProps) {
  return (
    <View style={styles.container}>
      <SymbolView
        name={{ ios: 'magnifyingglass', android: 'search', web: 'search' }}
        tintColor={colors.text.tertiary}
        size={20}
      />
      <TextInput
        accessibilityLabel="Search articles"
        autoCapitalize="none"
        onChangeText={onChangeText}
        placeholder="Search articles, models, companies..."
        placeholderTextColor={colors.text.tertiary}
        returnKeyType="search"
        style={styles.input}
        value={value}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    margin: spacing.lg,
    marginBottom: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: radius.full,
    borderColor: colors.border.default,
    borderWidth: 1,
    backgroundColor: colors.background.tertiary,
  },
  input: {
    flex: 1,
    minHeight: 48,
    color: colors.text.primary,
    fontFamily: typography.fontFamily.regular,
    fontSize: typography.size.base,
  },
});
