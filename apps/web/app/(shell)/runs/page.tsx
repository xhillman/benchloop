import { RunsWorkspace } from "@/components/runs/runs-workspace";
import { ErrorState } from "@/components/states/error-state";
import {
  ApiClientError,
  type ExperimentResponse,
  type RunHistoryResponse,
} from "@/lib/api/client";
import { getApiClient } from "@/lib/api/server";

export default async function RunsPage() {
  let bootstrapError: string | null = null;
  let experiments: ExperimentResponse[] = [];
  let runs: RunHistoryResponse[] = [];

  try {
    const apiClient = await getApiClient();
    [runs, experiments] = await Promise.all([
      apiClient.runs.list(),
      apiClient.experiments.list({ includeArchived: true }),
    ]);
  } catch (error) {
    if (error instanceof ApiClientError) {
      bootstrapError = `${error.message} (${error.status})`;
    } else {
      throw error;
    }
  }

  return (
    <>
      <section className="shell-panel page-header">
        <p className="eyebrow">Runs</p>
        <h1>Keep the execution record sortable, filterable, and reproducible.</h1>
        <p>
          This index is the first durable history surface for completed and failed runs. Use it to
          slice by experiment, provider, model, config, tag, and date, then open the exact run to
          inspect its immutable snapshot.
        </p>
      </section>

      {bootstrapError ? (
        <section className="state-card">
          <ErrorState
            message={bootstrapError}
            title="The runs index could not load"
          />
        </section>
      ) : (
        <RunsWorkspace initialExperiments={experiments} initialRuns={runs} />
      )}
    </>
  );
}
