"use client";

import { UserButton, useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { useAppShellState } from "@/components/providers/app-shell-provider";
import { productNavLinks } from "@/components/shell/nav-links";
import { publicAppConfig } from "@/lib/app-config";

type AppShellProps = {
  children: ReactNode;
};

function isActiveLink(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname() ?? "";
  const { isSignedIn } = useAuth();
  const { clearGlobalError, error, isLoading, pendingCount } = useAppShellState();

  return (
    <div className="shell-layout">
      <aside className="shell-sidebar">
        <div>
          <span className="brand-mark">Benchloop</span>
          <h2>Product shell</h2>
          <p>
            Stable navigation and shared state for the API-first experimentation workflow.
          </p>
        </div>

        <nav aria-label="Primary" className="shell-nav">
          {productNavLinks.map((link) => (
            <Link
              key={link.href}
              className={`shell-nav-link${isActiveLink(pathname, link.href) ? " is-active" : ""}`}
              href={link.href}
            >
              <span>{link.label}</span>
              <span>{link.description}</span>
            </Link>
          ))}
        </nav>

        <div className="shell-footer">
          {isSignedIn ? (
            <div className="shell-auth-card">
              <div>
                <span className="section-kicker">Session</span>
                <p>Active Clerk session</p>
              </div>
              <UserButton />
            </div>
          ) : (
            <div className="shell-auth-card">
              <div>
                <span className="section-kicker">Route gating</span>
                <p>Protected product routes redirect through Clerk.</p>
              </div>
              <Link className="cta-link secondary shell-auth-link" href={publicAppConfig.clerkSignInUrl}>
                Sign in
              </Link>
            </div>
          )}
        </div>
      </aside>

      <div className="shell-main">
        <header className="shell-topbar">
          <div>
            <p className="eyebrow">Benchloop workbench</p>
            <h1>FastAPI-first experiment shell</h1>
            <p className="status-copy">
              The shell owns navigation, Clerk session framing, and reusable loading or error
              surfaces.
            </p>
          </div>
          <div className="shell-pill">Protected by Clerk</div>
        </header>

        {isLoading ? (
          <div aria-live="polite" className="shell-loading-bar">
            Tracking {pendingCount} active shell operation{pendingCount === 1 ? "" : "s"}.
          </div>
        ) : null}

        {error ? (
          <div className="shell-banner" role="alert">
            <div>
              <strong>{error.title}</strong>
              {error.detail ? <span>{error.detail}</span> : null}
            </div>
            <button onClick={clearGlobalError} type="button">
              Dismiss
            </button>
          </div>
        ) : null}

        <main className="shell-content">{children}</main>
      </div>
    </div>
  );
}
