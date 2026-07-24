import { useCallback, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useAuthStore } from "../store/auth";
import { useToast } from "./useToast";

export function useAuth() {
  const store = useAuthStore();
  const toast = useToast();
  const navigate = useNavigate();

  const login = useCallback(
    async (username: string, password: string) => {
      const tokenRes = await api.auth.login({ username, password });
      store.setAuth(
        { id: 0, username, email: "", is_admin: false, roles: [], permissions: [] },
        tokenRes.access_token,
        tokenRes.refresh_token,
      );
      const user = await api.auth.me();
      store.setUser(user);
      toast.success(`Welcome, ${user.username}`);
      navigate("/");
    },
    [store, toast, navigate],
  );

  const register = useCallback(
    async (username: string, email: string, password: string) => {
      await api.auth.register({ username, email, password });
      toast.success("Registration successful! Please log in.");
      navigate("/login");
    },
    [toast, navigate],
  );

  const logout = useCallback(() => {
    store.logout();
    toast.info("Logged out");
    navigate("/login");
  }, [store, toast, navigate]);

  const refreshUser = useCallback(async () => {
    if (store.accessToken) {
      try {
        const user = await api.auth.me();
        store.setUser(user);
      } catch {
        store.logout();
      }
    }
  }, [store]);

  useEffect(() => {
    if (store.isAuthenticated) {
      refreshUser();
    }
  }, []);

  const hasPermission = useCallback(
    (permission: string) => {
      if (!store.user) return false;
      if (store.user.is_admin) return true;
      return store.user.permissions.includes(permission);
    },
    [store.user],
  );

  const hasRole = useCallback(
    (role: string) => {
      if (!store.user) return false;
      if (store.user.is_admin) return true;
      return store.user.roles.includes(role);
    },
    [store.user],
  );

  return {
    ...store,
    login,
    register,
    logout,
    refreshUser,
    hasPermission,
    hasRole,
  };
}
