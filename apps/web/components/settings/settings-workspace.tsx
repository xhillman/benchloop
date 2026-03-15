"use client";

import { startTransition, useState, type FormEvent } from "react";

import { useAppShellState } from "@/components/providers/app-shell-provider";
import { EmptyState } from "@/components/states/empty-state";
import { useApiClient } from "@/lib/api/browser";
import {
  ApiClientError,
  type UpdateUserSettingsRequest,
  type UserProviderCredentialResponse,
  type UserSettingsResponse,
} from "@/lib/api/client";

type SettingsWorkspaceProps = {
  initialCredentials: UserProviderCredentialResponse[];
  initialSettings: UserSettingsResponse;
};

type FeedbackState =
  | {
      tone: "error" | "success";
      message: string;
    }
  | null;

const providerOptions = [
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Anthropic" },
];

function normalizeOptionalText(value: string) {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

function sortCredentials(credentials: UserProviderCredentialResponse[]) {
  return [...credentials].sort((left, right) => {
    const providerComparison = left.provider.localeCompare(right.provider);

    if (providerComparison !== 0) {
      return providerComparison;
    }

    return left.created_at.localeCompare(right.created_at);
  });
}

function formatProvider(provider: string | null) {
  if (!provider) {
    return "Not set";
  }

  const option = providerOptions.find((candidate) => candidate.value === provider);
  return option?.label ?? provider;
}

function formatValidationStatus(status: string) {
  switch (status) {
    case "valid":
      return "Valid";
    case "invalid":
      return "Invalid";
    default:
      return "Not validated";
  }
}

function formatTimestamp(value: string | null) {
  if (!value) {
    return "Not yet checked";
  }

  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function validationBadgeClass(validationStatus: string) {
  switch (validationStatus) {
    case "valid":
      return "credential-status credential-status-valid";
    case "invalid":
      return "credential-status credential-status-invalid";
    default:
      return "credential-status credential-status-pending";
  }
}

export function SettingsWorkspace({
  initialCredentials,
  initialSettings,
}: SettingsWorkspaceProps) {
  const apiClient = useApiClient();
  const { clearGlobalError, setGlobalError, startLoading, stopLoading } = useAppShellState();

  const [settings, setSettings] = useState<UserSettingsResponse>(initialSettings);
  const [credentials, setCredentials] = useState(() => sortCredentials(initialCredentials));
  const [feedback, setFeedback] = useState<FeedbackState>(null);
  const [activeAction, setActiveAction] = useState<string | null>(null);

  const [defaultProvider, setDefaultProvider] = useState(initialSettings.default_provider ?? "");
  const [defaultModel, setDefaultModel] = useState(initialSettings.default_model ?? "");
  const [timezone, setTimezone] = useState(initialSettings.timezone ?? "UTC");

  const [credentialProvider, setCredentialProvider] = useState(providerOptions[0]?.value ?? "");
  const [credentialLabel, setCredentialLabel] = useState("");
  const [credentialApiKey, setCredentialApiKey] = useState("");

  const [replacementCredentialId, setReplacementCredentialId] = useState<string | null>(null);
  const [replacementLabel, setReplacementLabel] = useState("");
  const [replacementApiKey, setReplacementApiKey] = useState("");

  const configuredCredentials = credentials.length;
  const validatedCredentials = credentials.filter(
    (credential) => credential.validation_status === "valid",
  ).length;

  async function runMutation<T>({
    actionKey,
    errorTitle,
    successMessage,
    work,
    commit,
  }: {
    actionKey: string;
    errorTitle: string;
    successMessage: string;
    work: () => Promise<T>;
    commit: (result: T) => void;
  }) {
    clearGlobalError();
    setFeedback(null);
    setActiveAction(actionKey);
    startLoading();

    try {
      const result = await work();

      startTransition(() => {
        commit(result);
        setFeedback({
          tone: "success",
          message: successMessage,
        });
      });
    } catch (error) {
      const detail =
        error instanceof ApiClientError ? `${error.message} (${error.status})` : "Request failed.";

      setFeedback({
        tone: "error",
        message: detail,
      });
      setGlobalError({
        title: errorTitle,
        detail,
      });
    } finally {
      stopLoading();
      setActiveAction(null);
    }
  }

  function handleSaveDefaults(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const payload: UpdateUserSettingsRequest = {
      default_provider: normalizeOptionalText(defaultProvider),
      default_model: normalizeOptionalText(defaultModel),
      timezone: normalizeOptionalText(timezone),
    };

    void runMutation({
      actionKey: "save-defaults",
      errorTitle: "Could not save default settings",
      successMessage: "Default preferences saved.",
      work: () => apiClient.settings.update(payload),
      commit: (nextSettings) => {
        setSettings(nextSettings);
        setDefaultProvider(nextSettings.default_provider ?? "");
        setDefaultModel(nextSettings.default_model ?? "");
        setTimezone(nextSettings.timezone ?? "UTC");
      },
    });
  }

  function handleCreateCredential(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    void runMutation({
      actionKey: "create-credential",
      errorTitle: "Could not add provider credential",
      successMessage: "Credential stored for future runs.",
      work: () =>
        apiClient.settings.createCredential({
          provider: credentialProvider,
          api_key: credentialApiKey,
          key_label: normalizeOptionalText(credentialLabel),
        }),
      commit: (createdCredential) => {
        setCredentials((current) => sortCredentials([...current, createdCredential]));
        setCredentialLabel("");
        setCredentialApiKey("");
      },
    });
  }

  function handleValidateCredential(credentialId: string) {
    void runMutation({
      actionKey: `validate-${credentialId}`,
      errorTitle: "Could not validate provider credential",
      successMessage: "Credential validated successfully.",
      work: () => apiClient.settings.validateCredential(credentialId),
      commit: (validatedCredential) => {
        setCredentials((current) =>
          sortCredentials(
            current.map((credential) =>
              credential.id === credentialId ? validatedCredential : credential,
            ),
          ),
        );
      },
    });
  }

  function handleDeleteCredential(credentialId: string) {
    void runMutation({
      actionKey: `delete-${credentialId}`,
      errorTitle: "Could not delete provider credential",
      successMessage: "Credential removed from future runs.",
      work: () => apiClient.settings.deleteCredential(credentialId),
      commit: () => {
        setCredentials((current) =>
          current.filter((credential) => credential.id !== credentialId),
        );

        if (replacementCredentialId === credentialId) {
          setReplacementCredentialId(null);
          setReplacementLabel("");
          setReplacementApiKey("");
        }
      },
    });
  }

  function handleSubmitReplacement(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!replacementCredentialId) {
      return;
    }

    const credentialId = replacementCredentialId;

    void runMutation({
      actionKey: `replace-${credentialId}`,
      errorTitle: "Could not replace provider credential",
      successMessage: "Credential replaced. Validation has been reset.",
      work: () =>
        apiClient.settings.replaceCredential(credentialId, {
          api_key: replacementApiKey,
          key_label: normalizeOptionalText(replacementLabel),
        }),
      commit: (replacedCredential) => {
        setCredentials((current) =>
          sortCredentials(
            current.map((credential) =>
              credential.id === credentialId ? replacedCredential : credential,
            ),
          ),
        );
        setReplacementCredentialId(null);
        setReplacementLabel("");
        setReplacementApiKey("");
      },
    });
  }

  return (
    <div className="settings-shell">
      <section className="three-column-grid settings-summary-grid">
        <article className="shell-panel settings-summary-card">
          <p className="section-kicker">Default lane</p>
          <h2>{formatProvider(settings.default_provider)}</h2>
          <p className="status-copy">
            Model: {settings.default_model ?? "Choose a model when you need one."}
          </p>
        </article>

        <article className="shell-panel settings-summary-card">
          <p className="section-kicker">Credential ledger</p>
          <h2>{configuredCredentials}</h2>
          <p className="status-copy">
            {configuredCredentials === 1 ? "credential is" : "credentials are"} on file for future
            runs.
          </p>
        </article>

        <article className="shell-panel settings-summary-card">
          <p className="section-kicker">Validation posture</p>
          <h2>{validatedCredentials}</h2>
          <p className="status-copy">
            {validatedCredentials === 1 ? "credential is" : "credentials are"} confirmed against a
            live provider.
          </p>
        </article>
      </section>

      {feedback ? (
        <div
          className={`settings-feedback settings-feedback-${feedback.tone}`}
          role={feedback.tone === "error" ? "alert" : "status"}
        >
          {feedback.message}
        </div>
      ) : null}

      <section className="two-column-grid settings-setup-grid">
        <article className="shell-panel settings-card">
          <div className="settings-card-header">
            <div>
              <p className="section-kicker">Defaults</p>
              <h2>Guide new configs toward the right baseline.</h2>
            </div>
            <span className="shell-pill">FastAPI-backed</span>
          </div>

          <form className="settings-form" onSubmit={handleSaveDefaults}>
            <fieldset className="settings-fieldset" disabled={activeAction !== null}>
              <div className="settings-field-grid">
                <label className="settings-field">
                  <span>Default provider</span>
                  <select
                    name="default-provider"
                    onChange={(event) => setDefaultProvider(event.target.value)}
                    value={defaultProvider}
                  >
                    <option value="">No default provider</option>
                    {providerOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="settings-field">
                  <span>Timezone</span>
                  <input
                    name="timezone"
                    onChange={(event) => setTimezone(event.target.value)}
                    placeholder="UTC"
                    value={timezone}
                  />
                </label>
              </div>

              <label className="settings-field">
                <span>Default model</span>
                <input
                  name="default-model"
                  onChange={(event) => setDefaultModel(event.target.value)}
                  placeholder="gpt-4.1-mini"
                  value={defaultModel}
                />
              </label>

              <p className="settings-note">
                Defaults live at the account level so the web client and future agent callers stay
                aligned.
              </p>

              <div className="settings-action-row">
                <button className="settings-primary-action" type="submit">
                  Save defaults
                </button>
              </div>
            </fieldset>
          </form>
        </article>

        <article className="shell-panel settings-card settings-card-accent">
          <div className="settings-card-header">
            <div>
              <p className="section-kicker">New credential</p>
              <h2>Add a provider key without exposing it again.</h2>
            </div>
            <span className="shell-pill">Encrypted at rest</span>
          </div>

          <form className="settings-form" onSubmit={handleCreateCredential}>
            <fieldset className="settings-fieldset" disabled={activeAction !== null}>
              <div className="settings-field-grid">
                <label className="settings-field">
                  <span>Credential provider</span>
                  <select
                    name="credential-provider"
                    onChange={(event) => setCredentialProvider(event.target.value)}
                    value={credentialProvider}
                  >
                    {providerOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="settings-field">
                  <span>Label</span>
                  <input
                    name="credential-label"
                    onChange={(event) => setCredentialLabel(event.target.value)}
                    placeholder="Primary key"
                    value={credentialLabel}
                  />
                </label>
              </div>

              <label className="settings-field">
                <span>API key</span>
                <input
                  name="credential-api-key"
                  onChange={(event) => setCredentialApiKey(event.target.value)}
                  placeholder="Paste the provider key"
                  type="password"
                  value={credentialApiKey}
                />
              </label>

              <p className="settings-note">
                Validation status is stored separately, so rotation always resets the key back to a
                known unverified state.
              </p>

              <div className="settings-action-row">
                <button className="settings-primary-action" type="submit">
                  Add credential
                </button>
              </div>
            </fieldset>
          </form>
        </article>
      </section>

      <section className="shell-panel settings-card">
        <div className="settings-card-header">
          <div>
            <p className="section-kicker">Credential ledger</p>
            <h2>Inspect masked keys, validation state, and rotation history.</h2>
          </div>
          <span className="shell-pill">{configuredCredentials} active</span>
        </div>

        {credentials.length === 0 ? (
          <EmptyState
            action={
              <button
                className="settings-primary-action"
                onClick={() => {
                  clearGlobalError();
                  setFeedback(null);
                }}
                type="button"
              >
                Clear banners
              </button>
            }
            description="Saved provider keys will appear here with masked values, timestamps, and validation results."
            label="Credential ledger"
            title="No provider credentials saved yet"
          />
        ) : (
          <div className="settings-credential-grid">
            {credentials.map((credential) => {
              const isReplacing = replacementCredentialId === credential.id;

              return (
                <article className="credential-card" key={credential.id}>
                  <div className="credential-card-header">
                    <div>
                      <p className="section-kicker">{formatProvider(credential.provider)}</p>
                      <h3>{credential.key_label ?? "Unlabeled key"}</h3>
                    </div>
                    <span className={validationBadgeClass(credential.validation_status)}>
                      {formatValidationStatus(credential.validation_status)}
                    </span>
                  </div>

                  <dl className="credential-metadata">
                    <div>
                      <dt>Masked key</dt>
                      <dd>{credential.masked_api_key}</dd>
                    </div>
                    <div>
                      <dt>Last validated</dt>
                      <dd>{formatTimestamp(credential.last_validated_at)}</dd>
                    </div>
                    <div>
                      <dt>Updated</dt>
                      <dd>{formatTimestamp(credential.updated_at)}</dd>
                    </div>
                  </dl>

                  <div className="settings-action-row">
                    <button
                      className="settings-secondary-action"
                      onClick={() => handleValidateCredential(credential.id)}
                      type="button"
                    >
                      Validate key
                    </button>
                    <button
                      className="settings-secondary-action"
                      onClick={() => {
                        setReplacementCredentialId(credential.id);
                        setReplacementLabel(credential.key_label ?? "");
                        setReplacementApiKey("");
                      }}
                      type="button"
                    >
                      Replace key
                    </button>
                    <button
                      className="settings-danger-action"
                      onClick={() => handleDeleteCredential(credential.id)}
                      type="button"
                    >
                      Delete key
                    </button>
                  </div>

                  {isReplacing ? (
                    <form className="replacement-form" onSubmit={handleSubmitReplacement}>
                      <fieldset className="settings-fieldset" disabled={activeAction !== null}>
                        <div className="settings-field-grid">
                          <label className="settings-field">
                            <span>Replacement label</span>
                            <input
                              name={`replacement-label-${credential.id}`}
                              onChange={(event) => setReplacementLabel(event.target.value)}
                              value={replacementLabel}
                            />
                          </label>

                          <label className="settings-field">
                            <span>New API key</span>
                            <input
                              name={`replacement-api-key-${credential.id}`}
                              onChange={(event) => setReplacementApiKey(event.target.value)}
                              type="password"
                              value={replacementApiKey}
                            />
                          </label>
                        </div>

                        <div className="settings-action-row">
                          <button className="settings-primary-action" type="submit">
                            Save replacement
                          </button>
                          <button
                            className="settings-secondary-action"
                            onClick={() => {
                              setReplacementCredentialId(null);
                              setReplacementLabel("");
                              setReplacementApiKey("");
                            }}
                            type="button"
                          >
                            Cancel
                          </button>
                        </div>
                      </fieldset>
                    </form>
                  ) : null}
                </article>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
