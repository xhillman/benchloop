import { EmptyState } from "@/components/states/empty-state";

export default function ExperimentsPage() {
  return (
    <>
      <section className="shell-panel page-header">
        <p className="eyebrow">Experiments</p>
        <h1>Organize the work before you execute it.</h1>
        <p>
          This route will house experiment CRUD, test cases, and config surfaces. For B006 it
          exists as a stable shell destination with reusable empty-state treatment.
        </p>
      </section>

      <section className="state-card">
        <EmptyState
          label="Experiments"
          title="No experiments are defined yet"
          description="C006 through C008 will fill this route with the core lab entities. The app shell is already in place so those contracts can stay feature-focused."
        />
      </section>
    </>
  );
}
