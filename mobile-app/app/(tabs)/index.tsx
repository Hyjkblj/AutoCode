import { Text, View } from '@/components/Themed';
import { useAuth } from '@/contexts/AuthContext';
import { StyleSheet } from 'react-native';

export default function HomeScreen() {
  const { session, selectedProjectId, projects } = useAuth();
  const project = projects.find((p) => p.id === selectedProjectId);

  return (
    <View style={styles.container}>
      <Text style={styles.title}>首页</Text>
      <Text style={styles.line}>
        已登录：<Text style={styles.em}>{session?.displayName ?? '—'}</Text>
      </Text>
      <Text style={styles.line}>
        当前项目：<Text style={styles.em}>{project?.name ?? '未选择'}</Text>
      </Text>
      <View style={styles.hint} lightColor="#f0f4f8" darkColor="#1a1a1a">
        <Text style={styles.hintText}>
          PR-2：请到「任务」页用自然语言发起任务，查看列表与详情中的进度条与日志（当前为本地模拟轮询，后续对接控制面）。
        </Text>
      </View>
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
  line: {
    fontSize: 16,
    marginBottom: 10,
  },
  em: {
    fontWeight: '600',
  },
  hint: {
    marginTop: 24,
    padding: 14,
    borderRadius: 12,
  },
  hintText: {
    fontSize: 14,
    lineHeight: 20,
    opacity: 0.9,
  },
});
