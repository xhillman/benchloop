import { EmptyState } from "@/components/states/empty-state";

export default function SettingsPage() {
  return (
    <>
      <section className="shell-panel page-header">
        <p className="eyebrow">Settings</p>
        <h1>Keep credentials and defaults behind one predictable surface.</h1>
        <p>
          The settings route is reserved now so provider credential flows can drop into the shared
          shell without adding another navigation pattern later.
        </p>
      </section>

      <section className="state-card">
        <EmptyState
          label="Settings"
          title="Provider preferences are not wired yet"
          description="The settings contract will add credential management, validation status, and default provider or model controls in a later slice."
        />
      </section>
    </>
  );
}
