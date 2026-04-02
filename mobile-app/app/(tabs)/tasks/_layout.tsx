import { Stack } from 'expo-router';

export default function TasksStackLayout() {
  return (
    <Stack>
      <Stack.Screen name="index" options={{ title: '任务' }} />
      <Stack.Screen name="[id]" options={{ title: '任务详情' }} />
    </Stack>
  );
}
