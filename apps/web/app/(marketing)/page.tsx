import Link from "next/link";

import { publicAppConfig } from "@/lib/app-config";

export default function HomePage() {
  return (
    <main className="marketing-page">
      <div className="marketing-shell">
        <header className="marketing-topbar">
          <div>
            <span className="brand-mark">Benchloop</span>
          </div>
          <div className="pill">FastAPI-first client shell</div>
        </header>

        <section className="hero-grid">
          <div className="hero-copy">
            <p className="eyebrow">B006 Product Shell</p>
            <h1>Run the web app like a disciplined notebook, not a pile of tabs.</h1>
            <p>
              This scaffold establishes the shared navigation, route groups, and reusable
              state surfaces for the experiment loop. Feature pages stay thin while the FastAPI
              product core remains the system of record.
            </p>
            <div className="pill-row">
              <span className="pill">Dashboard</span>
              <span className="pill">Experiments</span>
              <span className="pill">Runs</span>
              <span className="pill">Settings</span>
            </div>
            <div className="cta-row">
              <Link className="cta-link primary" href="/dashboard">
                Open shell
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
                <strong>Clerk wiring lands in B007</strong>
              </div>
            </div>
          </aside>
        </section>

        <section className="section-grid">
          <article className="panel-card">
            <p className="section-kicker">Route groups</p>
            <h2>Public and shell routes split early.</h2>
            <p>
              The root page stays public while the main app shell lives under a dedicated group
              that can take Clerk protection in the next backlog item.
            </p>
          </article>

          <article className="panel-card">
            <p className="section-kicker">Global state</p>
            <h2>Loading and error state are centralized.</h2>
            <p>
              Shared UI state exists now so the later API client can raise actionable failures
              instead of burying them inside leaf components.
            </p>
          </article>

          <article className="panel-card">
            <p className="section-kicker">UI primitives</p>
            <h2>Empty, loading, and error surfaces are reusable.</h2>
            <p>
              Feature work can plug into consistent status cards instead of inventing page-by-page
              placeholders.
            </p>
          </article>
        </section>
      </div>
    </main>
  );
}
