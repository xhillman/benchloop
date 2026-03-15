import Link from "next/link";

import { ExperimentDetailShell } from "@/components/experiments/experiment-detail-shell";
import { ErrorState } from "@/components/states/error-state";
import { ApiClientError, type ExperimentResponse, type TestCaseResponse } from "@/lib/api/client";
import { getApiClient } from "@/lib/api/server";

type ExperimentDetailPageProps = {
  params: Promise<{
    experimentId: string;
  }>;
};

export default async function ExperimentDetailPage({ params }: ExperimentDetailPageProps) {
  const { experimentId } = await params;
  let bootstrapError: string | null = null;
  let experiment: ExperimentResponse | null = null;
  let testCases: TestCaseResponse[] = [];

  try {
    const apiClient = await getApiClient();
    [experiment, testCases] = await Promise.all([
      apiClient.experiments.get(experimentId),
      apiClient.experiments.listTestCases(experimentId),
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
          This route is the hub for the experiment. The overview is live now and the later tabs are
          in place so test cases, configs, runs, and compare can land without changing navigation.
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
        <ExperimentDetailShell initialExperiment={experiment} initialTestCases={testCases} />
      )}
    </>
  );
}
