export const colors = {
  background: {
    primary: '#0D0D0F',
    secondary: '#141416',
    tertiary: '#1C1C1F',
    overlay: 'rgba(0,0,0,0.6)',
  },
  border: {
    subtle: 'rgba(255,255,255,0.06)',
    default: 'rgba(255,255,255,0.10)',
    strong: 'rgba(255,255,255,0.18)',
  },
  text: {
    primary: '#F0EFE9',
    secondary: '#9A9890',
    tertiary: '#85827B',
    inverse: '#0D0D0F',
  },
  category: {
    models: { bg: '#1A1030', text: '#A78BFA', dot: '#7C3AED' },
    research: { bg: '#0F1E2E', text: '#60A5FA', dot: '#2563EB' },
    tools: { bg: '#0D1F18', text: '#34D399', dot: '#059669' },
    cloud: { bg: '#1A1A0A', text: '#FCD34D', dot: '#D97706' },
    industry: { bg: '#1F0D0D', text: '#F87171', dot: '#DC2626' },
    other: { bg: '#1A1A1A', text: '#9CA3AF', dot: '#4B5563' },
  },
  importance: {
    1: '#4B5563',
    2: '#6B7280',
    3: '#D97706',
    4: '#EA580C',
    5: '#EF4444',
  },
  accent: '#7C3AED',
  accentSoft: '#2D1F4E',
  success: '#059669',
  warning: '#D97706',
  error: '#DC2626',
};

export const typography = {
  fontFamily: {
    regular: 'Inter_400Regular',
    medium: 'Inter_500Medium',
    semibold: 'Inter_600SemiBold',
    bold: 'Inter_700Bold',
    mono: 'SpaceMono',
  },
  size: {
    xs: 11,
    sm: 13,
    base: 15,
    md: 17,
    lg: 20,
    xl: 24,
    '2xl': 30,
  },
  lineHeight: {
    tight: 1.2,
    normal: 1.5,
    relaxed: 1.75,
  },
};

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  '2xl': 32,
  '3xl': 48,
};

export const radius = {
  sm: 6,
  md: 10,
  lg: 14,
  xl: 20,
  full: 9999,
};

export const animation = {
  fast: 150,
  normal: 250,
  slow: 400,
  spring: { damping: 15, stiffness: 150 },
};
