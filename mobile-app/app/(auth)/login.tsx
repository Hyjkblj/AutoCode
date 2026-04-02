import { Text, View } from '@/components/Themed';
import { useAuth } from '@/contexts/AuthContext';
import Colors from '@/constants/Colors';
import { useColorScheme } from '@/components/useColorScheme';
import { useState } from 'react';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  TextInput,
} from 'react-native';

export default function LoginScreen() {
  const colorScheme = useColorScheme() ?? 'light';
  const colors = Colors[colorScheme];
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async () => {
    setError(null);
    setSubmitting(true);
    try {
      await login(username, password);
    } catch (e) {
      setError(e instanceof Error ? e.message : '登录失败');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={[styles.flex, { backgroundColor: colors.background }]}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <View style={styles.inner}>
        <Text style={styles.title}>AutoCode</Text>
        <Text style={styles.subtitle}>登录后选择项目（PR-1 占位：后续对接控制面 API）</Text>

        <TextInput
          placeholder="用户名"
          placeholderTextColor={colorScheme === 'dark' ? '#888' : '#999'}
          autoCapitalize="none"
          autoCorrect={false}
          value={username}
          onChangeText={setUsername}
          style={[
            styles.input,
            { color: colors.text, borderColor: colorScheme === 'dark' ? '#444' : '#ddd' },
          ]}
        />
        <TextInput
          placeholder="密码"
          placeholderTextColor={colorScheme === 'dark' ? '#888' : '#999'}
          secureTextEntry
          value={password}
          onChangeText={setPassword}
          style={[
            styles.input,
            { color: colors.text, borderColor: colorScheme === 'dark' ? '#444' : '#ddd' },
          ]}
        />

        {error ? (
          <Text style={styles.error} lightColor="#b00020" darkColor="#ff8a80">
            {error}
          </Text>
        ) : null}

        <Pressable
          onPress={onSubmit}
          disabled={submitting}
          style={({ pressed }) => [
            styles.button,
            { backgroundColor: colors.tint, opacity: pressed || submitting ? 0.75 : 1 },
          ]}>
          {submitting ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.buttonText} lightColor="#fff" darkColor="#111">
              登录
            </Text>
          )}
        </Pressable>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  inner: {
    flex: 1,
    justifyContent: 'center',
    paddingHorizontal: 28,
    maxWidth: 420,
    width: '100%',
    alignSelf: 'center',
  },
  title: {
    fontSize: 28,
    fontWeight: '700',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 14,
    opacity: 0.75,
    marginBottom: 28,
  },
  input: {
    borderWidth: 1,
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 16,
    marginBottom: 12,
  },
  error: {
    marginBottom: 12,
    fontSize: 14,
  },
  button: {
    borderRadius: 10,
    paddingVertical: 14,
    alignItems: 'center',
    marginTop: 8,
  },
  buttonText: {
    fontSize: 16,
    fontWeight: '600',
  },
});
