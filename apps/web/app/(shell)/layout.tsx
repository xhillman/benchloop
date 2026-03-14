import type { ReactNode } from "react";

import { AppShell } from "@/components/shell/app-shell";

type ProductShellLayoutProps = {
  children: ReactNode;
};

export default function ProductShellLayout({ children }: ProductShellLayoutProps) {
  return <AppShell>{children}</AppShell>;
}
