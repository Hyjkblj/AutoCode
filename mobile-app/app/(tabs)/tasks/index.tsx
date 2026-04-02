import { Text, View } from '@/components/Themed';
import { useAuth } from '@/contexts/AuthContext';
import { useTasks } from '@/contexts/TaskContext';
import Colors from '@/constants/Colors';
import { useColorScheme } from '@/components/useColorScheme';
import { Link, useRouter } from 'expo-router';
import { useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  StyleSheet,
  TextInput,
} from 'react-native';

function statusLabel(s: string): string {
  switch (s) {
    case 'queued':
      return '排队';
    case 'running':
      return '进行中';
    case 'succeeded':
      return '完成';
    case 'failed':
      return '失败';
    default:
      return s;
  }
}

export default function TasksIndexScreen() {
  const colorScheme = useColorScheme() ?? 'light';
  const colors = Colors[colorScheme];
  const router = useRouter();
  const { selectedProjectId, projects } = useAuth();
  const { tasksForProject, createTask, tasksReady } = useTasks();
  const project = projects.find((p) => p.id === selectedProjectId);
  const list = selectedProjectId ? tasksForProject(selectedProjectId) : [];
  const [prompt, setPrompt] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onCreate = async () => {
    if (!selectedProjectId) return;
    setError(null);
    setBusy(true);
    try {
      const id = await createTask(selectedProjectId, prompt);
      setPrompt('');
      router.push(`/tasks/${id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : '创建失败');
    } finally {
      setBusy(false);
    }
  };

  if (!selectedProjectId) {
    return (
      <View style={styles.center}>
        <Text style={styles.muted}>请先在「项目」页选择一个项目。</Text>
        <Link href="/projects" asChild>
          <Pressable style={[styles.linkBtn, { borderColor: colors.tint }]}>
            <Text style={{ color: colors.tint, fontWeight: '600' }}>去选择项目</Text>
          </Pressable>
        </Link>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.sub}>
        当前项目：<Text style={styles.em}>{project?.name ?? selectedProjectId}</Text>
      </Text>

      <TextInput
        placeholder="用自然语言描述要生成的内容（占位：后续对接控制面创建任务 API）"
        placeholderTextColor={colorScheme === 'dark' ? '#888' : '#999'}
        multiline
        value={prompt}
        onChangeText={setPrompt}
        style={[
          styles.input,
          { color: colors.text, borderColor: colorScheme === 'dark' ? '#444' : '#ddd' },
        ]}
      />
      {error ? (
        <Text style={styles.err} lightColor="#b00020" darkColor="#ff8a80">
          {error}
        </Text>
      ) : null}
      <Pressable
        onPress={() => void onCreate()}
        disabled={busy || !tasksReady}
        style={({ pressed }) => [
          styles.primaryBtn,
          { backgroundColor: colors.tint, opacity: pressed || busy || !tasksReady ? 0.75 : 1 },
        ]}>
        {busy ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.primaryBtnText} lightColor="#fff" darkColor="#111">
            发起任务
          </Text>
        )}
      </Pressable>

      <Text style={styles.sectionTitle}>任务列表</Text>
      <FlatList
        data={list}
        keyExtractor={(item) => item.id}
        ListEmptyComponent={
          <Text style={styles.muted}>暂无任务，输入描述后点击「发起任务」。</Text>
        }
        contentContainerStyle={styles.listContent}
        renderItem={({ item }) => (
          <Link href={`/tasks/${item.id}`} asChild>
            <Pressable
              style={({ pressed }) => [
                styles.row,
                {
                  borderColor: colorScheme === 'dark' ? '#444' : '#e8e8e8',
                  opacity: pressed ? 0.85 : 1,
                },
              ]}>
              <Text style={styles.rowPrompt} numberOfLines={2}>
                {item.prompt}
              </Text>
              <Text style={[styles.rowMeta, { color: colors.tint }]}>
                {statusLabel(item.status)} · {item.progress}%
              </Text>
            </Pressable>
          </Link>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16, paddingTop: 12 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },
  sub: { fontSize: 14, marginBottom: 12, opacity: 0.85 },
  em: { fontWeight: '700' },
  input: {
    minHeight: 96,
    textAlignVertical: 'top',
    borderWidth: 1,
    borderRadius: 12,
    padding: 12,
    fontSize: 15,
    marginBottom: 10,
  },
  err: { marginBottom: 8, fontSize: 14 },
  primaryBtn: {
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
    marginBottom: 20,
  },
  primaryBtnText: { fontSize: 16, fontWeight: '700' },
  sectionTitle: { fontSize: 16, fontWeight: '700', marginBottom: 10 },
  listContent: { paddingBottom: 24 },
  row: {
    borderWidth: 1,
    borderRadius: 12,
    padding: 14,
    marginBottom: 10,
  },
  rowPrompt: { fontSize: 15, marginBottom: 8 },
  rowMeta: { fontSize: 13, fontWeight: '600' },
  muted: { fontSize: 14, opacity: 0.7, textAlign: 'center' },
  linkBtn: {
    marginTop: 16,
    paddingVertical: 12,
    paddingHorizontal: 20,
    borderRadius: 10,
    borderWidth: 1,
  },
});
