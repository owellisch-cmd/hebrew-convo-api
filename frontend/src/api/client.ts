import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export const api = axios.create({
  baseURL: API_BASE_URL,
  // Render's free tier spins the backend down after ~15 minutes idle and takes
  // roughly a minute to wake. Without an explicit ceiling the browser hangs
  // indefinitely; 90s is long enough to survive a cold start and short enough
  // that a genuinely dead backend reports itself instead of spinning forever.
  timeout: 90_000,
});

/**
 * Fire-and-forget ping that wakes a sleeping backend while the user is still
 * reading the landing page, so their first real request isn't the one that
 * pays the cold-start cost. Failure is ignored on purpose — this is a warm-up,
 * not a health gate.
 */
export function wakeBackend(): void {
  api.get("/health").catch(() => undefined);
}

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("token");
      if (window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  },
);
