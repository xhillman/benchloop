import { EmptyState } from "@/components/states/empty-state";

export default function RunsPage() {
  return (
    <>
      <section className="shell-panel page-header">
        <p className="eyebrow">Runs</p>
        <h1>Inspect output, latency, and reproducibility from one lane.</h1>
        <p>
          Execution and rerun features land later. This route group keeps a dedicated area ready
          for compare-heavy workflows without restructuring the shell.
        </p>
      </section>

      <section className="state-card">
        <EmptyState
          label="Runs"
          title="No run history exists yet"
          description="Run snapshots, provider responses, and rerun actions will attach to this section once the execution contracts are implemented."
        />
      </section>
    </>
  );
}
