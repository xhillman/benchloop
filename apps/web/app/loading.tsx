import { LoadingState } from "@/components/states/loading-state";

export default function Loading() {
  return (
    <main className="marketing-page">
      <div className="marketing-shell">
        <div className="state-card">
          <LoadingState
            label="Loading shell"
            title="Preparing the workbench"
            description="Benchloop is mounting the shared shell and route groups."
          />
        </div>
      </div>
    </main>
  );
}
