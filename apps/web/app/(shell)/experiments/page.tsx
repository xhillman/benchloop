import { ExperimentsWorkspace } from "@/components/experiments/experiments-workspace";
import { ErrorState } from "@/components/states/error-state";
import { ApiClientError, type ExperimentResponse } from "@/lib/api/client";
import { getApiClient } from "@/lib/api/server";

const emptyExperiments: ExperimentResponse[] = [];

export default async function ExperimentsPage() {
  let initialExperiments = emptyExperiments;
  let bootstrapError: string | null = null;

  try {
    const apiClient = await getApiClient();
    initialExperiments = await apiClient.experiments.list();
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
        <p className="eyebrow">Experiments</p>
        <h1>Organize the work before you execute it.</h1>
        <p>
          Experiments are the top-level container for prompts, configs, test cases, runs, and later
          compare workflows. This page now keeps creation and filtering on one API-backed surface.
        </p>
      </section>

      {bootstrapError ? (
        <section className="state-card">
          <ErrorState
            message={bootstrapError}
            title="The experiments surface could not load its FastAPI bootstrap data"
          />
        </section>
      ) : (
        <ExperimentsWorkspace initialExperiments={initialExperiments} />
      )}
    </>
  );
}
