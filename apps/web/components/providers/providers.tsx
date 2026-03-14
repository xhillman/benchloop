"use client";

import type { ReactNode } from "react";

import { AppShellProvider } from "@/components/providers/app-shell-provider";

type ProvidersProps = {
  children: ReactNode;
};

export function Providers({ children }: ProvidersProps) {
  return <AppShellProvider>{children}</AppShellProvider>;
}
