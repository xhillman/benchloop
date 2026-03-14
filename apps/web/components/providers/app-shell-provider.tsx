"use client";

import { createContext, useContext, useState, type ReactNode } from "react";

type GlobalShellError = {
  title: string;
  detail?: string;
};

type AppShellStateValue = {
  isLoading: boolean;
  pendingCount: number;
  error: GlobalShellError | null;
  startLoading: () => void;
  stopLoading: () => void;
  setGlobalError: (error: GlobalShellError | null) => void;
  clearGlobalError: () => void;
};

const AppShellStateContext = createContext<AppShellStateValue | null>(null);

type AppShellProviderProps = {
  children: ReactNode;
};

export function AppShellProvider({ children }: AppShellProviderProps) {
  const [pendingCount, setPendingCount] = useState(0);
  const [error, setError] = useState<GlobalShellError | null>(null);

  const value: AppShellStateValue = {
    isLoading: pendingCount > 0,
    pendingCount,
    error,
    startLoading: () => {
      setPendingCount((current) => current + 1);
    },
    stopLoading: () => {
      setPendingCount((current) => Math.max(0, current - 1));
    },
    setGlobalError: (nextError) => {
      setError(nextError);
    },
    clearGlobalError: () => {
      setError(null);
    },
  };

  return <AppShellStateContext.Provider value={value}>{children}</AppShellStateContext.Provider>;
}

export function useAppShellState() {
  const value = useContext(AppShellStateContext);

  if (!value) {
    throw new Error("useAppShellState must be used within AppShellProvider");
  }

  return value;
}
