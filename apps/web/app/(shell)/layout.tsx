import { auth } from "@clerk/nextjs/server";
import type { ReactNode } from "react";

import { AppShell } from "@/components/shell/app-shell";

type ProductShellLayoutProps = {
  children: ReactNode;
};

export default async function ProductShellLayout({ children }: ProductShellLayoutProps) {
  await auth.protect();

  return <AppShell>{children}</AppShell>;
}
