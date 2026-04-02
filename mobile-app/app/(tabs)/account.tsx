import { Text, View } from '@/components/Themed';
import { useAuth } from '@/contexts/AuthContext';
import Colors from '@/constants/Colors';
import { useColorScheme } from '@/components/useColorScheme';
import { Platform, Pressable, StyleSheet } from 'react-native';

export default function AccountScreen() {
  const colorScheme = useColorScheme() ?? 'light';
  const colors = Colors[colorScheme];
  const { session, logout } = useAuth();

  return (
    <View style={styles.container}>
      <Text style={styles.title}>我的</Text>
      <View style={styles.card} lightColor="#f5f5f5" darkColor="#1c1c1c">
        <Text style={styles.label}>显示名</Text>
        <Text style={styles.value}>{session?.displayName ?? '—'}</Text>
        <Text style={styles.label}>Token（占位）</Text>
        <Text style={styles.mono} numberOfLines={1}>
          {session?.accessToken ?? '—'}
        </Text>
      </View>
      <Pressable
        onPress={() => void logout()}
        style={({ pressed }) => [
          styles.logout,
          { backgroundColor: '#c62828', opacity: pressed ? 0.85 : 1 },
        ]}>
        <Text style={styles.logoutText} lightColor="#fff" darkColor="#fff">
          退出登录
        </Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 20,
    paddingTop: 16,
  },
  title: {
    fontSize: 22,
    fontWeight: '700',
    marginBottom: 16,
  },
  card: {
    borderRadius: 12,
    padding: 16,
    marginBottom: 24,
  },
  label: {
    fontSize: 12,
    opacity: 0.7,
    marginBottom: 4,
  },
  value: {
    fontSize: 18,
    fontWeight: '600',
    marginBottom: 14,
  },
  mono: {
    fontSize: 12,
    opacity: 0.85,
    fontFamily: Platform.select({ ios: 'Menlo', android: 'monospace', default: 'monospace' }),
  },
  logout: {
    borderRadius: 10,
    paddingVertical: 14,
    alignItems: 'center',
  },
  logoutText: {
    fontSize: 16,
    fontWeight: '600',
  },
});
