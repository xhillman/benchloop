import Link from "next/link";

import { RunDetail } from "@/components/runs/run-detail";
import { ErrorState } from "@/components/states/error-state";
import { ApiClientError, type RunDetailResponse } from "@/lib/api/client";
import { getApiClient } from "@/lib/api/server";

type RunDetailPageProps = {
  params: Promise<{
    runId: string;
  }>;
};

export default async function RunDetailPage({ params }: RunDetailPageProps) {
  const { runId } = await params;
  let bootstrapError: string | null = null;
  let run: RunDetailResponse | null = null;

  try {
    const apiClient = await getApiClient();
    run = await apiClient.runs.get(runId);
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
        <p className="eyebrow">Run detail</p>
        <h1>Inspect the immutable record behind one execution.</h1>
        <p>
          This page shows the source-of-truth prompts, snapshots, inputs, outputs, usage, latency,
          cost, and failure state that were stored for the run, plus a rerun action that reuses the
          stored snapshot instead of today&apos;s mutable config state.
        </p>
        <div className="cta-row">
          <Link className="cta-link secondary" href="/runs">
            Back to runs
          </Link>
        </div>
      </section>

      {bootstrapError || !run ? (
        <section className="state-card">
          <ErrorState
            message={bootstrapError ?? "Run detail data was not available."}
            title="The run detail surface could not load"
          />
        </section>
      ) : (
        <RunDetail run={run} />
      )}
    </>
  );
}
