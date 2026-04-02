import AsyncStorage from '@react-native-async-storage/async-storage';
import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';

const STORAGE_SESSION = 'autocode.session.v1';
const STORAGE_PROJECT = 'autocode.selectedProjectId.v1';

export type Session = {
  accessToken: string;
  displayName: string;
};

export type Project = {
  id: string;
  name: string;
};

const MOCK_PROJECTS: Project[] = [
  { id: 'p1', name: '示例项目 Alpha' },
  { id: 'p2', name: '示例项目 Beta' },
  { id: 'p3', name: '微信小程序 · 商城' },
];

type AuthContextValue = {
  session: Session | null;
  selectedProjectId: string | null;
  projects: Project[];
  isReady: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  selectProject: (id: string) => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [rawSession, rawProject] = await Promise.all([
          AsyncStorage.getItem(STORAGE_SESSION),
          AsyncStorage.getItem(STORAGE_PROJECT),
        ]);
        if (cancelled) return;
        if (rawSession) setSession(JSON.parse(rawSession) as Session);
        if (rawProject) setSelectedProjectId(rawProject);
      } finally {
        if (!cancelled) setIsReady(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const u = username.trim();
    const p = password.trim();
    if (!u || !p) {
      throw new Error('请输入用户名和密码');
    }
    const next: Session = {
      accessToken: `mock.${Date.now()}`,
      displayName: u,
    };
    setSession(next);
    await AsyncStorage.setItem(STORAGE_SESSION, JSON.stringify(next));
    const pid = (await AsyncStorage.getItem(STORAGE_PROJECT)) ?? MOCK_PROJECTS[0].id;
    setSelectedProjectId(pid);
    await AsyncStorage.setItem(STORAGE_PROJECT, pid);
  }, []);

  const logout = useCallback(async () => {
    setSession(null);
    setSelectedProjectId(null);
    await Promise.all([
      AsyncStorage.removeItem(STORAGE_SESSION),
      AsyncStorage.removeItem(STORAGE_PROJECT),
    ]);
  }, []);

  const selectProject = useCallback(async (id: string) => {
    setSelectedProjectId(id);
    await AsyncStorage.setItem(STORAGE_PROJECT, id);
  }, []);

  const value = useMemo(
    () => ({
      session,
      selectedProjectId,
      projects: MOCK_PROJECTS,
      isReady,
      login,
      logout,
      selectProject,
    }),
    [session, selectedProjectId, isReady, login, logout, selectProject]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return ctx;
}
