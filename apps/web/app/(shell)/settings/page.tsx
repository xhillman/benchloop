import { SettingsWorkspace } from "@/components/settings/settings-workspace";
import { ErrorState } from "@/components/states/error-state";
import {
  ApiClientError,
  type UserProviderCredentialResponse,
  type UserSettingsResponse,
} from "@/lib/api/client";
import { getApiClient } from "@/lib/api/server";

const emptySettings: UserSettingsResponse = {
  default_provider: null,
  default_model: null,
  timezone: "UTC",
};

const emptyCredentials: UserProviderCredentialResponse[] = [];

export default async function SettingsPage() {
  let initialSettings = emptySettings;
  let initialCredentials = emptyCredentials;
  let bootstrapError: string | null = null;

  try {
    const apiClient = await getApiClient();
    const [settings, credentials] = await Promise.all([
      apiClient.settings.get(),
      apiClient.settings.listCredentials(),
    ]);

    initialSettings = settings;
    initialCredentials = credentials;
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
        <p className="eyebrow">Settings</p>
        <h1>Configure defaults and provider access.</h1>
        <p>
          This lane keeps account-level defaults, encrypted provider credentials, and validation
          metadata on one API-backed surface.
        </p>
      </section>

      {bootstrapError ? (
        <section className="state-card">
          <ErrorState
            message={bootstrapError}
            title="The settings surface could not load its FastAPI bootstrap data"
          />
        </section>
      ) : (
        <SettingsWorkspace
          initialCredentials={initialCredentials}
          initialSettings={initialSettings}
        />
      )}
    </>
  );
}
