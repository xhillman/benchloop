import Link from "next/link";

import { ExperimentDetailShell } from "@/components/experiments/experiment-detail-shell";
import { ErrorState } from "@/components/states/error-state";
import {
  ApiClientError,
  type ConfigResponse,
  type ExperimentResponse,
  type RunHistoryResponse,
  type TestCaseResponse,
} from "@/lib/api/client";
import { getApiClient } from "@/lib/api/server";

type ExperimentDetailPageProps = {
  params: Promise<{
    experimentId: string;
  }>;
};

export default async function ExperimentDetailPage({ params }: ExperimentDetailPageProps) {
  const { experimentId } = await params;
  let bootstrapError: string | null = null;
  let configs: ConfigResponse[] = [];
  let experiment: ExperimentResponse | null = null;
  let runs: RunHistoryResponse[] = [];
  let testCases: TestCaseResponse[] = [];

  try {
    const apiClient = await getApiClient();
    [experiment, testCases, configs, runs] = await Promise.all([
      apiClient.experiments.get(experimentId),
      apiClient.experiments.listTestCases(experimentId),
      apiClient.experiments.listConfigs(experimentId),
      apiClient.runs.list({ experimentIds: [experimentId] }),
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
        <p className="eyebrow">Experiment detail</p>
        <h1>Use one shell to steer the rest of the experiment workflow.</h1>
        <p>
          This route is the hub for the experiment. Overview, test cases, configs, and single-shot
          run launch are live now, and compare plus manual evaluation stay on the same API-backed
          surface.
        </p>
        <div className="cta-row">
          <Link className="cta-link secondary" href="/experiments">
            Back to experiments
          </Link>
        </div>
      </section>

      {bootstrapError || !experiment ? (
        <section className="state-card">
          <ErrorState
            message={bootstrapError ?? "Experiment data was not available."}
            title="The experiment detail surface could not load"
          />
        </section>
      ) : (
        <ExperimentDetailShell
          initialConfigs={configs}
          initialExperiment={experiment}
          initialRuns={runs}
          initialTestCases={testCases}
        />
      )}
    </>
  );
}
