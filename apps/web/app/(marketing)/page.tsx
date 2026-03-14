import { auth } from "@clerk/nextjs/server";
import Link from "next/link";

import { publicAppConfig } from "@/lib/app-config";

export default async function HomePage() {
  const { userId } = await auth();
  const isSignedIn = Boolean(userId);

  return (
    <main className="marketing-page">
      <div className="marketing-shell">
        <header className="marketing-topbar">
          <div>
            <span className="brand-mark">Benchloop</span>
          </div>
          <div className="pill">{isSignedIn ? "Active Clerk session" : "Public visitor"}</div>
        </header>

        <section className="hero-grid">
          <div className="hero-copy">
            <p className="eyebrow">B007 Clerk Integration</p>
            <h1>Run the web app like a disciplined notebook, not a pile of tabs.</h1>
            <p>
              Clerk now gates the product shell while the public landing page stays open. The web
              app can route users into a real sign-in flow without moving product behavior out of
              FastAPI.
            </p>
            <div className="pill-row">
              <span className="pill">Dashboard</span>
              <span className="pill">Experiments</span>
              <span className="pill">Runs</span>
              <span className="pill">Settings</span>
            </div>
            <div className="cta-row">
              <Link
                className="cta-link primary"
                href={isSignedIn ? "/dashboard" : publicAppConfig.clerkSignInUrl}
              >
                {isSignedIn ? "Open dashboard" : "Sign in to Benchloop"}
              </Link>
              <a className="cta-link secondary" href={publicAppConfig.apiBaseUrl}>
                View API base
              </a>
            </div>
          </div>

          <aside className="hero-panel">
            <h2>Scaffold status</h2>
            <div className="metric-stack">
              <div className="metric-row">
                <span>Client app</span>
                <strong>{publicAppConfig.appUrl}</strong>
              </div>
              <div className="metric-row">
                <span>API target</span>
                <strong>{publicAppConfig.apiBaseUrl}</strong>
              </div>
              <div className="metric-row">
                <span>Auth lane</span>
                <strong>{isSignedIn ? "Active Clerk session" : "Public visitor"}</strong>
              </div>
            </div>
          </aside>
        </section>

        <section className="section-grid">
          <article className="panel-card">
            <p className="section-kicker">Route groups</p>
            <h2>Public and shell routes are split and enforced.</h2>
            <p>
              The root page stays public while the main app shell sits behind Clerk-backed route
              protection and dedicated auth entrypoints.
            </p>
          </article>

          <article className="panel-card">
            <p className="section-kicker">Auth flow</p>
            <h2>Sign-in redirects land users inside the shell.</h2>
            <p>
              The shell can now depend on a Clerk session and later backlog items can attach the
              typed FastAPI client to that authenticated context.
            </p>
          </article>

          <article className="panel-card">
            <p className="section-kicker">UI primitives</p>
            <h2>Signed-in shell behavior is visible in the shared chrome.</h2>
            <p>
              The protected shell keeps reusable status surfaces while exposing a live session
              affordance instead of placeholder auth copy.
            </p>
          </article>
        </section>
      </div>
    </main>
  );
}
