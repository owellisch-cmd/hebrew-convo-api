import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api } from "../api/client";
import type { UserOut } from "../types";

interface AuthContextValue {
  user: UserOut | null;
  loading: boolean;
  login: (token: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserOut | null>(null);
  const [loading, setLoading] = useState(true);

  async function fetchMe() {
    try {
      const { data } = await api.get<UserOut>("/auth/me");
      setUser(data);
    } catch {
      setUser(null);
      localStorage.removeItem("token");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (localStorage.getItem("token")) {
      fetchMe();
    } else {
      setLoading(false);
    }
  }, []);

  async function login(token: string) {
    localStorage.setItem("token", token);
    await fetchMe();
  }

  function logout() {
    localStorage.removeItem("token");
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
