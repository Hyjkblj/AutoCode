import { Text, View } from '@/components/Themed';
import { useTasks } from '@/contexts/TaskContext';
import Colors from '@/constants/Colors';
import { useColorScheme } from '@/components/useColorScheme';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect } from 'react';
import { Pressable, ScrollView, StyleSheet } from 'react-native';

export default function TaskDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const { getTask } = useTasks();
  const task = id ? getTask(id) : undefined;
  const colorScheme = useColorScheme() ?? 'light';
  const colors = Colors[colorScheme];

  useEffect(() => {
    if (id && !task) {
      const t = setTimeout(() => router.replace('/tasks'), 400);
      return () => clearTimeout(t);
    }
  }, [id, task, router]);

  if (!task) {
    return (
      <View style={styles.center}>
        <Text>加载中或任务不存在…</Text>
      </View>
    );
  }

  const barColor =
    task.status === 'failed' ? '#c62828' : task.status === 'succeeded' ? '#2e7d32' : colors.tint;

  return (
    <ScrollView contentContainerStyle={styles.content}>
      <Text style={styles.title}>任务</Text>
      <Text style={styles.prompt}>{task.prompt}</Text>

      <View style={styles.metaRow}>
        <Text style={styles.meta}>状态：{task.status}</Text>
        <Text style={styles.meta}>进度：{task.progress}%</Text>
      </View>

      <View style={[styles.track, { backgroundColor: colorScheme === 'dark' ? '#333' : '#e8e8e8' }]}>
        <View style={[styles.fill, { width: `${task.progress}%`, backgroundColor: barColor }]} />
      </View>

      <Text style={styles.logTitle}>日志（轮询模拟）</Text>
      {task.logs.map((line, i) => (
        <Text key={`${i}-${line}`} style={styles.logLine}>
          · {line}
        </Text>
      ))}

      <Pressable
        onPress={() => router.back()}
        style={({ pressed }) => [
          styles.back,
          { borderColor: colors.tint, opacity: pressed ? 0.8 : 1 },
        ]}>
        <Text style={{ color: colors.tint, fontWeight: '600' }}>返回列表</Text>
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },
  content: { padding: 16, paddingBottom: 32 },
  title: { fontSize: 14, opacity: 0.7, marginBottom: 6 },
  prompt: { fontSize: 18, fontWeight: '700', marginBottom: 14, lineHeight: 26 },
  metaRow: { flexDirection: 'row', gap: 16, marginBottom: 12 },
  meta: { fontSize: 14 },
  track: { height: 10, borderRadius: 6, overflow: 'hidden', marginBottom: 22 },
  fill: { height: '100%', borderRadius: 6 },
  logTitle: { fontSize: 16, fontWeight: '700', marginBottom: 10 },
  logLine: { fontSize: 14, lineHeight: 22, marginBottom: 4, opacity: 0.9 },
  back: {
    marginTop: 24,
    alignSelf: 'flex-start',
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderRadius: 10,
    borderWidth: 1,
  },
});
