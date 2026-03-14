import { ErrorState } from "@/components/states/error-state";
import { EmptyState } from "@/components/states/empty-state";
import { publicAppConfig } from "@/lib/app-config";
import { ApiClientError } from "@/lib/api/client";
import { getApiClient } from "@/lib/api/server";

export default async function DashboardPage() {
  let apiBootstrap: {
    externalUserId: string;
    healthStatus: string;
    serviceName: string;
  } | null = null;
  let apiBootstrapError: string | null = null;

  try {
    const apiClient = await getApiClient();
    const [healthStatus, currentUser] = await Promise.all([
      apiClient.health.getStatus(),
      apiClient.auth.getMe(),
    ]);

    apiBootstrap = {
      externalUserId: currentUser.external_user_id,
      healthStatus: healthStatus.status,
      serviceName: healthStatus.service,
    };
  } catch (error) {
    if (error instanceof ApiClientError) {
      apiBootstrapError = `${error.message} (${error.status})`;
    } else {
      throw error;
    }
  }

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
          {apiBootstrap ? (
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
                <span>API health</span>
                <strong>
                  {apiBootstrap.healthStatus} via {apiBootstrap.serviceName}
                </strong>
              </div>
              <div className="status-item">
                <span>Authenticated subject</span>
                <strong>{apiBootstrap.externalUserId}</strong>
              </div>
            </div>
          ) : (
            <ErrorState
              title="The dashboard could not load its API bootstrap data"
              message={
                apiBootstrapError ??
                "The shared client should surface FastAPI failures as readable UI state."
              }
            />
          )}
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
