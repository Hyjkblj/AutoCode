import { Text, View } from '@/components/Themed';
import { useAuth } from '@/contexts/AuthContext';
import Colors from '@/constants/Colors';
import { useColorScheme } from '@/components/useColorScheme';
import { Pressable, StyleSheet } from 'react-native';

export default function ProjectsScreen() {
  const colorScheme = useColorScheme() ?? 'light';
  const colors = Colors[colorScheme];
  const { projects, selectedProjectId, selectProject } = useAuth();

  return (
    <View style={styles.container}>
      <Text style={styles.title}>选择项目</Text>
      <Text style={styles.sub}>点击一行切换当前项目（数据为占位列表，后续对接控制面）</Text>
      {projects.map((p) => {
        const active = p.id === selectedProjectId;
        return (
          <Pressable
            key={p.id}
            onPress={() => void selectProject(p.id)}
            style={({ pressed }) => [
              styles.row,
              {
                borderColor: active ? colors.tint : colorScheme === 'dark' ? '#444' : '#e0e0e0',
                backgroundColor: active
                  ? colorScheme === 'dark'
                    ? 'rgba(255,255,255,0.08)'
                    : 'rgba(47,149,220,0.12)'
                  : 'transparent',
                opacity: pressed ? 0.85 : 1,
              },
            ]}>
            <Text style={styles.rowTitle}>{p.name}</Text>
            {active ? (
              <Text style={[styles.badge, { color: colors.tint }]}>当前</Text>
            ) : null}
          </Pressable>
        );
      })}
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
    marginBottom: 8,
  },
  sub: {
    fontSize: 14,
    opacity: 0.75,
    marginBottom: 20,
  },
  row: {
    borderWidth: 1,
    borderRadius: 12,
    paddingVertical: 14,
    paddingHorizontal: 16,
    marginBottom: 10,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  rowTitle: {
    fontSize: 16,
    flex: 1,
    paddingRight: 12,
  },
  badge: {
    fontSize: 13,
    fontWeight: '600',
  },
});
