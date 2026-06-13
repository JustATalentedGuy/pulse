import * as Haptics from 'expo-haptics';

export async function lightHaptic() {
  try {
    await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
  } catch {
    // Haptics are optional on web and unsupported devices.
  }
}
