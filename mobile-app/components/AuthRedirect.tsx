import { useAuth } from '@/contexts/AuthContext';
import { useRouter, useSegments } from 'expo-router';
import { useEffect } from 'react';

/**
 * 未登录时进入 (auth)，已登录时离开 (auth)；与文档 PR-1 会话门禁一致。
 */
export function AuthRedirect() {
  const { session, isReady } = useAuth();
  const segments = useSegments();
  const router = useRouter();

  useEffect(() => {
    if (!isReady) return;
    const first = segments[0];
    const inAuth = first === '(auth)';
    if (!session && !inAuth) {
      router.replace('/(auth)/login');
    } else if (session && inAuth) {
      router.replace('/(tabs)');
    }
  }, [session, isReady, segments, router]);

  return null;
}
