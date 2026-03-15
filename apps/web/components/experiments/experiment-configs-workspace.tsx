"use client";

import { startTransition, useState, type FormEvent } from "react";

import { useAppShellState } from "@/components/providers/app-shell-provider";
import { EmptyState } from "@/components/states/empty-state";
import { useApiClient } from "@/lib/api/browser";
import {
  ApiClientError,
  type ConfigResponse,
  type CreateConfigRequest,
  type UpdateConfigRequest,
} from "@/lib/api/client";

type ExperimentConfigsWorkspaceProps = {
  experimentId: string;
  initialConfigs: ConfigResponse[];
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

const workflowOptions = [
  { value: "single_shot", label: "Single shot" },
  { value: "prompt_plus_context", label: "Prompt + context" },
  { value: "two_step_chain", label: "Two-step chain" },
];

function normalizeOptionalText(value: string) {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

function parseOptionalNumber(value: string) {
  const trimmed = value.trim();
  if (trimmed.length === 0) {
    return null;
  }

  return Number(trimmed);
}

function parseTags(value: string) {
  const tags = value
    .split(",")
    .map((tag) => tag.trim().toLowerCase())
    .filter((tag) => tag.length > 0);

  return Array.from(new Set(tags));
}

function serializeTags(tags: string[]) {
  return tags.join(", ");
}

function sortConfigs(configs: ConfigResponse[]) {
  return [...configs].sort((left, right) => {
    if (left.is_baseline !== right.is_baseline) {
      return Number(right.is_baseline) - Number(left.is_baseline);
    }

    const updatedComparison = right.updated_at.localeCompare(left.updated_at);
    if (updatedComparison !== 0) {
      return updatedComparison;
    }

    const nameComparison = left.name.localeCompare(right.name);
    if (nameComparison !== 0) {
      return nameComparison;
    }

    return left.version_label.localeCompare(right.version_label);
  });
}

function formatProvider(provider: string) {
  const option = providerOptions.find((candidate) => candidate.value === provider);
  return option?.label ?? provider;
}

function formatWorkflowMode(workflowMode: string) {
  const option = workflowOptions.find((candidate) => candidate.value === workflowMode);
  return option?.label ?? workflowMode;
}

function formatTimestamp(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function buildPromptPreview(value: string) {
  const compact = value.replace(/\s+/g, " ").trim();
  if (compact.length <= 140) {
    return compact;
  }
  return `${compact.slice(0, 137)}...`;
}

function nextVersionLabel(configs: ConfigResponse[]) {
  return `v${configs.length + 1}`;
}

export function ExperimentConfigsWorkspace({
  experimentId,
  initialConfigs,
}: ExperimentConfigsWorkspaceProps) {
  const apiClient = useApiClient();
  const { clearGlobalError, setGlobalError, startLoading, stopLoading } = useAppShellState();

  const [configs, setConfigs] = useState(() => sortConfigs(initialConfigs));
  const [editingId, setEditingId] = useState<string | null>(null);
  const [activeAction, setActiveAction] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<FeedbackState>(null);

  const [name, setName] = useState("");
  const [versionLabel, setVersionLabel] = useState(nextVersionLabel(initialConfigs));
  const [provider, setProvider] = useState(providerOptions[0]?.value ?? "openai");
  const [model, setModel] = useState("");
  const [workflowMode, setWorkflowMode] = useState(workflowOptions[0]?.value ?? "single_shot");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [userPromptTemplate, setUserPromptTemplate] = useState("");
  const [temperature, setTemperature] = useState("1");
  const [maxOutputTokens, setMaxOutputTokens] = useState("512");
  const [topP, setTopP] = useState("");
  const [description, setDescription] = useState("");
  const [tags, setTags] = useState("");
  const [isBaseline, setIsBaseline] = useState(false);

  const baselineCount = configs.filter((config) => config.is_baseline).length;
  const workflowCount = new Set(configs.map((config) => config.workflow_mode)).size;

  async function runTask<T>({
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

  function resetForm(nextConfigs = configs) {
    setEditingId(null);
    setName("");
    setVersionLabel(nextVersionLabel(nextConfigs));
    setProvider(providerOptions[0]?.value ?? "openai");
    setModel("");
    setWorkflowMode(workflowOptions[0]?.value ?? "single_shot");
    setSystemPrompt("");
    setUserPromptTemplate("");
    setTemperature("1");
    setMaxOutputTokens("512");
    setTopP("");
    setDescription("");
    setTags("");
    setIsBaseline(false);
  }

  function buildPayload(): CreateConfigRequest | UpdateConfigRequest {
    return {
      name,
      version_label: versionLabel,
      description: normalizeOptionalText(description),
      provider,
      model,
      workflow_mode: workflowMode,
      system_prompt: normalizeOptionalText(systemPrompt),
      user_prompt_template: userPromptTemplate,
      temperature: Number(temperature),
      max_output_tokens: Number(maxOutputTokens),
      top_p: parseOptionalNumber(topP),
      context_bundle_id: null,
      tags: parseTags(tags),
      is_baseline: isBaseline,
    };
  }

  function mergeConfig(nextConfig: ConfigResponse, currentConfigs: ConfigResponse[]) {
    const nextConfigs = currentConfigs.map((config) =>
      config.id === nextConfig.id
        ? nextConfig
        : nextConfig.is_baseline
          ? { ...config, is_baseline: false }
          : config,
    );

    if (!nextConfigs.some((config) => config.id === nextConfig.id)) {
      nextConfigs.unshift(nextConfig);
    }

    return sortConfigs(nextConfigs);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (editingId) {
      const payload = buildPayload();
      void runTask({
        actionKey: "save-config",
        errorTitle: "Could not save config",
        successMessage: "Config updated.",
        work: () => apiClient.experiments.updateConfig(experimentId, editingId, payload),
        commit: (updatedConfig) => {
          const nextConfigs = mergeConfig(updatedConfig, configs);
          setConfigs(nextConfigs);
          resetForm(nextConfigs);
        },
      });
      return;
    }

    const payload = buildPayload();
    void runTask({
      actionKey: "create-config",
      errorTitle: "Could not create config",
      successMessage: "Config created.",
      work: () => apiClient.experiments.createConfig(experimentId, payload),
      commit: (createdConfig) => {
        const nextConfigs = mergeConfig(createdConfig, configs);
        setConfigs(nextConfigs);
        resetForm(nextConfigs);
      },
    });
  }

  function handleEdit(config: ConfigResponse) {
    setEditingId(config.id);
    setName(config.name);
    setVersionLabel(config.version_label);
    setProvider(config.provider);
    setModel(config.model);
    setWorkflowMode(config.workflow_mode);
    setSystemPrompt(config.system_prompt ?? "");
    setUserPromptTemplate(config.user_prompt_template);
    setTemperature(String(config.temperature));
    setMaxOutputTokens(String(config.max_output_tokens));
    setTopP(config.top_p === null ? "" : String(config.top_p));
    setDescription(config.description ?? "");
    setTags(serializeTags(config.tags));
    setIsBaseline(config.is_baseline);
    setFeedback(null);
  }

  function handleClone(configId: string) {
    void runTask({
      actionKey: `clone-${configId}`,
      errorTitle: "Could not clone config",
      successMessage: "Config cloned.",
      work: () => apiClient.experiments.cloneConfig(experimentId, configId),
      commit: (clonedConfig) => {
        const nextConfigs = mergeConfig(clonedConfig, configs);
        setConfigs(nextConfigs);
      },
    });
  }

  function handleMarkBaseline(configId: string) {
    void runTask({
      actionKey: `baseline-${configId}`,
      errorTitle: "Could not mark baseline config",
      successMessage: "Baseline updated.",
      work: () => apiClient.experiments.markConfigBaseline(experimentId, configId),
      commit: (baselineConfig) => {
        const nextConfigs = mergeConfig(baselineConfig, configs);
        setConfigs(nextConfigs);
        if (editingId === baselineConfig.id) {
          setIsBaseline(true);
        }
      },
    });
  }

  function handleDelete(configId: string) {
    void runTask({
      actionKey: `delete-${configId}`,
      errorTitle: "Could not delete config",
      successMessage: "Config deleted.",
      work: async () => {
        await apiClient.experiments.deleteConfig(experimentId, configId);
      },
      commit: () => {
        const nextConfigs = configs.filter((config) => config.id !== configId);
        setConfigs(nextConfigs);
        if (editingId === configId) {
          resetForm(nextConfigs);
        }
      },
    });
  }

  const isEditing = editingId !== null;

  return (
    <div className="experiment-test-cases-layout" role="tabpanel">
      {feedback ? (
        <div
          className={`settings-feedback settings-feedback-${feedback.tone}`}
          role={feedback.tone === "error" ? "alert" : "status"}
        >
          {feedback.message}
        </div>
      ) : null}

      <section className="three-column-grid experiments-summary-grid">
        <article className="shell-panel experiments-summary-card">
          <p className="section-kicker">Configs in lane</p>
          <h3>{configs.length}</h3>
          <p className="status-copy">Keep editable config variants inside the experiment.</p>
        </article>

        <article className="shell-panel experiments-summary-card">
          <p className="section-kicker">Baseline markers</p>
          <h3>{baselineCount}</h3>
          <p className="status-copy">Use one visible baseline to anchor later run comparisons.</p>
        </article>

        <article className="shell-panel experiments-summary-card">
          <p className="section-kicker">Workflow mix</p>
          <h3>{workflowCount}</h3>
          <p className="status-copy">Single-shot, context, and chain modes can coexist here.</p>
        </article>
      </section>

      <section className="two-column-grid experiments-controls-grid">
        <article className="shell-panel experiments-card experiments-card-accent">
          <div className="settings-card-header">
            <div>
              <p className="section-kicker">Config editor</p>
              <h3>{isEditing ? "Revise the selected config." : "Add a reusable execution config."}</h3>
            </div>
            <p className="experiments-list-meta">
              Use short version labels like `v1`, `v2`, or `cheap-pass`.
            </p>
          </div>

          <form className="settings-form" onSubmit={handleSubmit}>
            <fieldset className="settings-fieldset" disabled={activeAction !== null}>
              <div className="settings-field-grid">
                <label className="settings-field">
                  <span>Name</span>
                  <input name="name" onChange={(event) => setName(event.target.value)} required value={name} />
                </label>

                <label className="settings-field">
                  <span>Version label</span>
                  <input
                    name="version_label"
                    onChange={(event) => setVersionLabel(event.target.value)}
                    required
                    value={versionLabel}
                  />
                </label>

                <label className="settings-field">
                  <span>Provider</span>
                  <select name="provider" onChange={(event) => setProvider(event.target.value)} value={provider}>
                    {providerOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="settings-field">
                  <span>Model</span>
                  <input name="model" onChange={(event) => setModel(event.target.value)} required value={model} />
                </label>

                <label className="settings-field">
                  <span>Workflow mode</span>
                  <select
                    name="workflow_mode"
                    onChange={(event) => setWorkflowMode(event.target.value)}
                    value={workflowMode}
                  >
                    {workflowOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="settings-field">
                  <span>Temperature</span>
                  <input
                    max="2"
                    min="0"
                    name="temperature"
                    onChange={(event) => setTemperature(event.target.value)}
                    required
                    step="0.1"
                    type="number"
                    value={temperature}
                  />
                </label>

                <label className="settings-field">
                  <span>Max output tokens</span>
                  <input
                    min="1"
                    name="max_output_tokens"
                    onChange={(event) => setMaxOutputTokens(event.target.value)}
                    required
                    type="number"
                    value={maxOutputTokens}
                  />
                </label>

                <label className="settings-field">
                  <span>Top p</span>
                  <input
                    max="1"
                    min="0"
                    name="top_p"
                    onChange={(event) => setTopP(event.target.value)}
                    placeholder="Optional"
                    step="0.05"
                    type="number"
                    value={topP}
                  />
                </label>
              </div>

              <label className="settings-field">
                <span>System prompt</span>
                <textarea
                  name="system_prompt"
                  onChange={(event) => setSystemPrompt(event.target.value)}
                  rows={4}
                  value={systemPrompt}
                />
              </label>

              <label className="settings-field">
                <span>User prompt template</span>
                <textarea
                  name="user_prompt_template"
                  onChange={(event) => setUserPromptTemplate(event.target.value)}
                  required
                  rows={5}
                  value={userPromptTemplate}
                />
                <small className="run-helper-copy">
                  Use `{"{{input}}"}` for the saved test case input in single-shot runs.
                </small>
              </label>

              <label className="settings-field">
                <span>Description</span>
                <textarea
                  name="description"
                  onChange={(event) => setDescription(event.target.value)}
                  rows={3}
                  value={description}
                />
              </label>

              <label className="settings-field">
                <span>Config tags</span>
                <input
                  name="tags"
                  onChange={(event) => setTags(event.target.value)}
                  placeholder="cheap, baseline"
                  value={tags}
                />
              </label>

              <label className="experiments-checkbox">
                <input
                  checked={isBaseline}
                  onChange={(event) => setIsBaseline(event.target.checked)}
                  type="checkbox"
                />
                <span>Set this config as the visible baseline for the experiment.</span>
              </label>
            </fieldset>

            <div className="settings-action-row">
              <button className="settings-primary-action" type="submit">
                {isEditing ? "Save config" : "Create config"}
              </button>
              {isEditing ? (
                <button className="settings-secondary-action" onClick={() => resetForm()} type="button">
                  Cancel edit
                </button>
              ) : null}
            </div>
          </form>
        </article>

        <article className="shell-panel experiments-card">
          <div className="experiments-list-header">
            <div>
              <p className="section-kicker">Config variants</p>
              <h3>Keep prompt, model, and parameter changes readable.</h3>
            </div>
            <p className="experiments-list-meta">{configs.length} saved</p>
          </div>

          {configs.length === 0 ? (
            <EmptyState
              description="Create the first config so this experiment has a reusable prompt and model setup ready for later runs."
              label="Configs"
              title="No configs yet"
            />
          ) : (
            <div className="experiments-card-grid">
              {configs.map((config) => (
                <article className="experiment-card test-case-card" key={config.id}>
                  <div className="experiment-card-header">
                    <div>
                      <p className="section-kicker">{config.version_label}</p>
                      <h3>{config.name}</h3>
                    </div>
                    <span className="state-badge">
                      {config.is_baseline ? "Baseline" : formatWorkflowMode(config.workflow_mode)}
                    </span>
                  </div>

                  <dl className="experiment-metadata">
                    <div>
                      <dt>Provider</dt>
                      <dd>
                        {formatProvider(config.provider)} · {config.model}
                      </dd>
                    </div>
                    <div>
                      <dt>Prompt preview</dt>
                      <dd>{buildPromptPreview(config.user_prompt_template)}</dd>
                    </div>
                    <div>
                      <dt>Generation params</dt>
                      <dd>
                        Temp {config.temperature} · Max {config.max_output_tokens}
                        {config.top_p === null ? "" : ` · Top p ${config.top_p}`}
                      </dd>
                    </div>
                    <div>
                      <dt>Tags</dt>
                      <dd>{config.tags.length > 0 ? serializeTags(config.tags) : "No tags yet."}</dd>
                    </div>
                    <div>
                      <dt>Description</dt>
                      <dd>{config.description ?? "No description recorded."}</dd>
                    </div>
                    <div>
                      <dt>Last updated</dt>
                      <dd>{formatTimestamp(config.updated_at)}</dd>
                    </div>
                  </dl>

                  <div className="settings-action-row">
                    <button className="settings-secondary-action" onClick={() => handleEdit(config)} type="button">
                      Edit config
                    </button>
                    <button
                      className="settings-secondary-action"
                      onClick={() => handleClone(config.id)}
                      type="button"
                    >
                      Clone config
                    </button>
                    <button
                      className="settings-secondary-action"
                      onClick={() => handleMarkBaseline(config.id)}
                      type="button"
                    >
                      Mark baseline
                    </button>
                    <button
                      className="settings-danger-action"
                      onClick={() => handleDelete(config.id)}
                      type="button"
                    >
                      Delete config
                    </button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </article>
      </section>
    </div>
  );
}
