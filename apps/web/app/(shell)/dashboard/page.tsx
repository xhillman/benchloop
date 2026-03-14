import { EmptyState } from "@/components/states/empty-state";
import { publicAppConfig } from "@/lib/app-config";

export default function DashboardPage() {
  return (
    <>
      <section className="shell-panel page-header">
        <p className="eyebrow">Dashboard</p>
        <h1>Experiment control plane</h1>
        <p>
          The shell is in place. Next backlog items can hang authenticated data views and API
          client behavior off this shared structure without rewriting navigation or state surfaces.
        </p>
      </section>

      <section className="two-column-grid">
        <article className="shell-panel">
          <p className="section-kicker">Foundation</p>
          <h2>FastAPI stays canonical.</h2>
          <p className="status-copy">
            The web app remains a client. API behavior, ownership rules, and provider execution
            stay on the backend.
          </p>
          <div className="status-list">
            <div className="status-item">
              <span>App URL</span>
              <strong>{publicAppConfig.appUrl}</strong>
            </div>
            <div className="status-item">
              <span>API base URL</span>
              <strong>{publicAppConfig.apiBaseUrl}</strong>
            </div>
            <div className="status-item">
              <span>Signed-in shell</span>
              <strong>Protected route group with Clerk session gating</strong>
            </div>
          </div>
        </article>

        <article className="shell-panel">
          <p className="section-kicker">Workflow lanes</p>
          <h2>Core sections are reserved now.</h2>
          <p className="status-copy">
            Dashboard, experiments, runs, and settings all have stable route surfaces so later
            contracts can fill them in without shifting the product shell.
          </p>
          <div className="status-list">
            <div className="status-item">
              <span>Experiments</span>
              <strong>Entity setup and organization</strong>
            </div>
            <div className="status-item">
              <span>Runs</span>
              <strong>Execution history and reruns</strong>
            </div>
            <div className="status-item">
              <span>Settings</span>
              <strong>Credentials and defaults</strong>
            </div>
          </div>
        </article>
      </section>

      <section className="state-card">
        <EmptyState
          label="Run history"
          title="No benchmark activity yet"
          description="Run records will appear here once the execution contracts land. The shell already has a stable placeholder for that shared empty state."
        />
      </section>
    </>
  );
}
