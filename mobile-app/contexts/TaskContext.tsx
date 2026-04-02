import AsyncStorage from '@react-native-async-storage/async-storage';
import { useAuth } from '@/contexts/AuthContext';
import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';

const STORAGE_TASKS = 'autocode.tasks.v1';

export type TaskStatus = 'queued' | 'running' | 'succeeded' | 'failed';

export type TaskItem = {
  id: string;
  projectId: string;
  prompt: string;
  status: TaskStatus;
  progress: number;
  logs: string[];
  createdAt: number;
  updatedAt: number;
};

type TaskContextValue = {
  tasks: TaskItem[];
  tasksReady: boolean;
  createTask: (projectId: string, prompt: string) => Promise<string>;
  getTask: (id: string) => TaskItem | undefined;
  tasksForProject: (projectId: string) => TaskItem[];
};

const TaskContext = createContext<TaskContextValue | null>(null);

function newId(): string {
  return `t_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

export function TaskProvider({ children }: { children: React.ReactNode }) {
  const { session, isReady: authReady } = useAuth();
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [tasksReady, setTasksReady] = useState(false);
  const prevSession = useRef<typeof session>(null);
  const promoteTimers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  useEffect(() => {
    if (!authReady) return;
    if (!session) {
      setTasks([]);
      setTasksReady(true);
      return;
    }
    let cancelled = false;
    (async () => {
      const raw = await AsyncStorage.getItem(STORAGE_TASKS);
      if (cancelled) return;
      if (raw) {
        try {
          const parsed = JSON.parse(raw) as TaskItem[];
          if (Array.isArray(parsed)) {
            const now = Date.now();
            setTasks(
              parsed.map((t) =>
                t.status === 'queued'
                  ? {
                      ...t,
                      status: 'running' as const,
                      progress: Math.max(5, t.progress),
                      logs: [...t.logs, '应用重启后继续执行（占位）'],
                      updatedAt: now,
                    }
                  : t
              )
            );
          }
        } catch {
          setTasks([]);
        }
      }
      setTasksReady(true);
    })();
    return () => {
      cancelled = true;
    };
  }, [authReady, session?.accessToken]);

  useEffect(() => {
    if (prevSession.current && !session) {
      promoteTimers.current.forEach((t) => clearTimeout(t));
      promoteTimers.current.clear();
      setTasks([]);
      void AsyncStorage.removeItem(STORAGE_TASKS);
    }
    prevSession.current = session;
  }, [session]);

  useEffect(() => {
    if (!tasksReady || !session) return;
    void AsyncStorage.setItem(STORAGE_TASKS, JSON.stringify(tasks));
  }, [tasks, tasksReady, session]);

  useEffect(() => {
    if (!session) return;
    const tick = setInterval(() => {
      setTasks((prev) => {
        let changed = false;
        const next = prev.map((t) => {
          if (t.status !== 'running') return t;
          const delta = 8 + Math.floor(Math.random() * 10);
          const np = Math.min(100, t.progress + delta);
          const logs = [...t.logs];
          if (np >= 28 && t.progress < 28) logs.push('分析需求…');
          if (np >= 55 && t.progress < 55) logs.push('生成代码与资源（占位）…');
          if (np >= 100 && t.progress < 100) logs.push('完成（模拟，后续对接控制面轮询/WebSocket）');
          changed = true;
          const status: TaskStatus = np >= 100 ? 'succeeded' : 'running';
          return {
            ...t,
            progress: np,
            status,
            logs,
            updatedAt: Date.now(),
          };
        });
        return changed ? next : prev;
      });
    }, 1200);
    return () => clearInterval(tick);
  }, [session]);

  const createTask = useCallback(async (projectId: string, prompt: string) => {
    const text = prompt.trim();
    if (!text) throw new Error('请输入任务描述');
    const id = newId();
    const now = Date.now();
    const item: TaskItem = {
      id,
      projectId,
      prompt: text,
      status: 'queued',
      progress: 0,
      logs: ['已加入队列'],
      createdAt: now,
      updatedAt: now,
    };
    setTasks((prev) => [item, ...prev]);

    const timer = setTimeout(() => {
      promoteTimers.current.delete(id);
      setTasks((prev) =>
        prev.map((t) =>
          t.id === id && t.status === 'queued'
            ? {
                ...t,
                status: 'running' as const,
                progress: 5,
                logs: [...t.logs, '开始执行…'],
                updatedAt: Date.now(),
              }
            : t
        )
      );
    }, 450);
    promoteTimers.current.set(id, timer);

    return id;
  }, []);

  const getTask = useCallback(
    (id: string) => tasks.find((t) => t.id === id),
    [tasks]
  );

  const tasksForProject = useCallback(
    (projectId: string) => tasks.filter((t) => t.projectId === projectId).sort((a, b) => b.createdAt - a.createdAt),
    [tasks]
  );

  const value = useMemo(
    () => ({
      tasks,
      tasksReady,
      createTask,
      getTask,
      tasksForProject,
    }),
    [tasks, tasksReady, createTask, getTask, tasksForProject]
  );

  return <TaskContext.Provider value={value}>{children}</TaskContext.Provider>;
}

export function useTasks() {
  const ctx = useContext(TaskContext);
  if (!ctx) throw new Error('useTasks must be used within TaskProvider');
  return ctx;
}
