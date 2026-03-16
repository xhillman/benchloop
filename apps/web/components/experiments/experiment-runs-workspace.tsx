"use client";

import { startTransition, useState } from "react";

import { useAppShellState } from "@/components/providers/app-shell-provider";
import { EmptyState } from "@/components/states/empty-state";
import { useApiClient } from "@/lib/api/browser";
import {
  ApiClientError,
  type ConfigResponse,
  type ContextBundleResponse,
  type RunResponse,
  type TestCaseResponse,
} from "@/lib/api/client";

type ExperimentRunsWorkspaceProps = {
  experimentId: string;
  initialContextBundles: ContextBundleResponse[];
  initialConfigs: ConfigResponse[];
  initialTestCases: TestCaseResponse[];
};

type FeedbackState =
  | {
      tone: "error" | "success";
      message: string;
    }
  | null;

function buildPreview(value: string) {
  const compact = value.replace(/\s+/g, " ").trim();
  if (compact.length <= 110) {
    return compact;
  }
  return `${compact.slice(0, 107)}...`;
}

function formatTimestamp(value: string | null) {
  if (!value) {
    return "Not started";
  }

  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function formatProvider(provider: string) {
  if (provider === "openai") {
    return "OpenAI";
  }
  if (provider === "anthropic") {
    return "Anthropic";
  }
  return provider;
}

function formatStatus(status: string) {
  return status.replace(/_/g, " ");
}

function formatCurrency(value: number | null) {
  if (value === null) {
    return "Unavailable";
  }

  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 4,
  }).format(value);
}

function sortTestCases(testCases: TestCaseResponse[]) {
  return [...testCases].sort((left, right) => {
    const updatedComparison = right.updated_at.localeCompare(left.updated_at);
    if (updatedComparison !== 0) {
      return updatedComparison;
    }

    return left.id.localeCompare(right.id);
  });
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

    return left.id.localeCompare(right.id);
  });
}

function sortContextBundles(contextBundles: ContextBundleResponse[]) {
  return [...contextBundles].sort((left, right) => {
    const updatedComparison = right.updated_at.localeCompare(left.updated_at);
    if (updatedComparison !== 0) {
      return updatedComparison;
    }

    return left.id.localeCompare(right.id);
  });
}

export function ExperimentRunsWorkspace({
  experimentId,
  initialContextBundles,
  initialConfigs,
  initialTestCases,
}: ExperimentRunsWorkspaceProps) {
  const apiClient = useApiClient();
  const { clearGlobalError, setGlobalError, startLoading, stopLoading } = useAppShellState();

  const testCases = sortTestCases(initialTestCases);
  const contextBundles = sortContextBundles(initialContextBundles);
  const launchableConfigs = sortConfigs(
    initialConfigs.filter(
      (config) =>
        config.workflow_mode === "prompt_plus_context" || config.workflow_mode === "single_shot",
    ),
  );
  const blockedConfigCount = initialConfigs.length - launchableConfigs.length;

  const [selectedTestCaseId, setSelectedTestCaseId] = useState<string | null>(testCases[0]?.id ?? null);
  const [selectedConfigIds, setSelectedConfigIds] = useState<Set<string>>(() => new Set());
  const [contextSource, setContextSource] = useState<"config_default" | "inline" | "saved_bundle">(
    "config_default",
  );
  const [selectedContextBundleId, setSelectedContextBundleId] = useState<string>(
    contextBundles[0]?.id ?? "",
  );
  const [inlineContextName, setInlineContextName] = useState("");
  const [inlineContextContent, setInlineContextContent] = useState("");
  const [inlineContextNotes, setInlineContextNotes] = useState("");
  const [latestRuns, setLatestRuns] = useState<RunResponse[]>([]);
  const [activeAction, setActiveAction] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<FeedbackState>(null);

  async function runTask({
    work,
    successMessage,
  }: {
    work: () => Promise<RunResponse[]>;
    successMessage: string;
  }) {
    clearGlobalError();
    setFeedback(null);
    setActiveAction("launch-runs");
    startLoading();

    try {
      const runs = await work();

      startTransition(() => {
        setLatestRuns(runs);
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
        title: "Could not launch runs",
        detail,
      });
    } finally {
      stopLoading();
      setActiveAction(null);
    }
  }

  function toggleConfigSelection(configId: string) {
    setSelectedConfigIds((current) => {
      const nextSelectedConfigIds = new Set(current);
      if (nextSelectedConfigIds.has(configId)) {
        nextSelectedConfigIds.delete(configId);
      } else {
        nextSelectedConfigIds.add(configId);
      }
      return nextSelectedConfigIds;
    });
  }

  function handleLaunch() {
    if (!selectedTestCaseId || selectedConfigIds.size === 0) {
      return;
    }

    const selectedConfigs = launchableConfigs.filter((config) => selectedConfigIds.has(config.id));
    const configIds = selectedConfigs.map((config) => config.id);
    const promptPlusContextConfigs = selectedConfigs.filter(
      (config) => config.workflow_mode === "prompt_plus_context",
    );
    const singleShotConfigs = selectedConfigs.filter((config) => config.workflow_mode === "single_shot");

    if (configIds.length === 0) {
      return;
    }

    if (contextSource !== "config_default" && singleShotConfigs.length > 0) {
      setFeedback({
        tone: "error",
        message:
          "Ad hoc context can only be used when every selected config uses prompt + context mode.",
      });
      return;
    }

    if (
      promptPlusContextConfigs.length > 0 &&
      contextSource === "config_default" &&
      promptPlusContextConfigs.some((config) => config.context_bundle_id === null)
    ) {
      setFeedback({
        tone: "error",
        message:
          "Selected prompt + context configs need a default context bundle or an ad hoc override.",
      });
      return;
    }

    if (
      promptPlusContextConfigs.length > 0 &&
      contextSource === "saved_bundle" &&
      selectedContextBundleId.length === 0
    ) {
      setFeedback({
        tone: "error",
        message: "Choose a saved context bundle before launching these runs.",
      });
      return;
    }

    if (
      promptPlusContextConfigs.length > 0 &&
      contextSource === "inline" &&
      inlineContextContent.trim().length === 0
    ) {
      setFeedback({
        tone: "error",
        message: "Inline context content is required before launching these runs.",
      });
      return;
    }

    const contextPayload =
      promptPlusContextConfigs.length === 0
        ? {}
        : contextSource === "saved_bundle"
          ? { context_bundle_id: selectedContextBundleId }
          : contextSource === "inline"
            ? {
                inline_context: {
                  name: inlineContextName.trim().length > 0 ? inlineContextName.trim() : null,
                  content_text: inlineContextContent.trim(),
                  notes: inlineContextNotes.trim().length > 0 ? inlineContextNotes.trim() : null,
                },
              }
            : {};

    if (configIds.length === 1) {
      const [configId] = configIds;
      void runTask({
        successMessage: "Run launched.",
        work: async () => [
          await apiClient.experiments.launchRun(experimentId, {
            test_case_id: selectedTestCaseId,
            config_id: configId,
            ...contextPayload,
          }),
        ],
      });
      return;
    }

    void runTask({
      successMessage: `${configIds.length} runs launched.`,
      work: () =>
        apiClient.experiments.launchBatchRuns(experimentId, {
          test_case_id: selectedTestCaseId,
          config_ids: configIds,
          ...contextPayload,
        }),
    });
  }

  const selectedConfigCount = selectedConfigIds.size;
  const selectedConfigs = launchableConfigs.filter((config) => selectedConfigIds.has(config.id));
  const selectedPromptPlusContextCount = selectedConfigs.filter(
    (config) => config.workflow_mode === "prompt_plus_context",
  ).length;
  const launchButtonLabel =
    selectedConfigCount === 1 ? "Run selected config" : "Run selected configs";

  return (
    <div className="run-launch-layout" role="tabpanel">
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
          <p className="section-kicker">Saved test cases</p>
          <h3>{testCases.length}</h3>
          <p className="status-copy">Choose one stable input before launching any config.</p>
        </article>

        <article className="shell-panel experiments-summary-card">
          <p className="section-kicker">Launchable configs</p>
          <h3>{launchableConfigs.length}</h3>
          <p className="status-copy">Single-shot and prompt + context configs can launch here.</p>
        </article>

        <article className="shell-panel experiments-summary-card">
          <p className="section-kicker">Blocked for later</p>
          <h3>{blockedConfigCount}</h3>
          <p className="status-copy">Two-step configs stay editable until their run mode lands.</p>
        </article>
      </section>

      <section className="two-column-grid experiments-controls-grid">
        <article className="shell-panel experiments-card experiments-card-accent">
          <div className="settings-card-header">
            <div>
              <p className="section-kicker">Test case target</p>
              <h3>Select one input for this launch.</h3>
            </div>
            <p className="experiments-list-meta">
              The selected test case is reused across every chosen config.
            </p>
          </div>

          {testCases.length === 0 ? (
            <EmptyState
              description="Create at least one test case before trying to launch a run."
              label="Test cases"
              title="No test cases ready"
            />
          ) : (
            <div className="run-select-list">
              {testCases.map((testCase) => (
                <label className="experiment-card run-select-card" key={testCase.id}>
                  <div className="experiments-checkbox test-case-select">
                    <input
                      checked={selectedTestCaseId === testCase.id}
                      name="selected_test_case"
                      onChange={() => setSelectedTestCaseId(testCase.id)}
                      type="radio"
                    />
                    <span>{buildPreview(testCase.input_text)}</span>
                  </div>

                  <dl className="experiment-metadata">
                    <div>
                      <dt>Expected output</dt>
                      <dd>{testCase.expected_output_text ?? "No expected output recorded."}</dd>
                    </div>
                    <div>
                      <dt>Tags</dt>
                      <dd>{testCase.tags.length > 0 ? testCase.tags.join(", ") : "No tags"}</dd>
                    </div>
                  </dl>
                </label>
              ))}
            </div>
          )}
        </article>

        <article className="shell-panel experiments-card">
          <div className="settings-card-header">
            <div>
              <p className="section-kicker">Config set</p>
              <h3>Pick one config or a comparison set.</h3>
            </div>
            <p className="experiments-list-meta">
              Multiple selections launch one owned run record per config.
            </p>
          </div>

          {launchableConfigs.length === 0 ? (
            <EmptyState
              description="Create a single-shot config before trying to launch a run."
              label="Configs"
              title="No launchable configs ready"
            />
          ) : (
            <>
              {blockedConfigCount > 0 ? (
                <p className="run-helper-copy">
                  {blockedConfigCount} config
                  {blockedConfigCount === 1 ? "" : "s"} use a later workflow mode and are excluded
                  from B025 launch.
                </p>
              ) : null}

              <div className="run-select-list">
                {launchableConfigs.map((config) => (
                  <label className="experiment-card run-select-card" key={config.id}>
                    <div className="experiments-checkbox">
                      <input
                        checked={selectedConfigIds.has(config.id)}
                        onChange={() => toggleConfigSelection(config.id)}
                        type="checkbox"
                      />
                      <span>
                        {config.name} {config.version_label}
                      </span>
                    </div>

                    <dl className="experiment-metadata">
                      <div>
                        <dt>Provider</dt>
                        <dd>
                          {formatProvider(config.provider)} / {config.model}
                        </dd>
                      </div>
                      <div>
                        <dt>Workflow</dt>
                        <dd>{config.workflow_mode.replace(/_/g, " ")}</dd>
                      </div>
                      <div>
                        <dt>Prompt preview</dt>
                        <dd>{buildPreview(config.user_prompt_template)}</dd>
                      </div>
                      <div>
                        <dt>Default context</dt>
                        <dd>
                          {config.context_bundle_id
                            ? (contextBundles.find((contextBundle) => contextBundle.id === config.context_bundle_id)
                                ?.name ?? "Attached bundle")
                            : "None"}
                        </dd>
                      </div>
                    </dl>
                  </label>
                ))}
              </div>

              <div className="run-launch-action-row">
                <p className="run-helper-copy">
                  {selectedConfigCount} config{selectedConfigCount === 1 ? "" : "s"} selected.
                </p>
                <button
                  className="cta-link primary"
                  disabled={
                    activeAction !== null || selectedTestCaseId === null || selectedConfigCount === 0
                  }
                  onClick={handleLaunch}
                  type="button"
                >
                  {launchButtonLabel}
                </button>
              </div>
            </>
          )}
        </article>
      </section>

      <section className="shell-panel experiments-card">
        <div className="settings-card-header">
          <div>
            <p className="section-kicker">Context injection</p>
            <h3>Use each config default or override it at launch time.</h3>
          </div>
          <p className="experiments-list-meta">
            {selectedPromptPlusContextCount > 0
              ? `${selectedPromptPlusContextCount} selected config${selectedPromptPlusContextCount === 1 ? "" : "s"} require prompt + context rules.`
              : "Select a prompt + context config to apply launch-time context controls."}
          </p>
        </div>

        <div className="settings-form">
          <label className="settings-field">
            <span>Context source</span>
            <select
              aria-label="Context source"
              name="context_source"
              onChange={(event) =>
                setContextSource(
                  event.target.value as "config_default" | "inline" | "saved_bundle",
                )
              }
              value={contextSource}
            >
              <option value="config_default">Use config default</option>
              <option value="saved_bundle">Use saved bundle</option>
              <option value="inline">Use inline context</option>
            </select>
          </label>

          {contextSource === "saved_bundle" ? (
            <label className="settings-field">
              <span>Saved context bundle</span>
              <select
                aria-label="Saved context bundle"
                name="selected_context_bundle_id"
                onChange={(event) => setSelectedContextBundleId(event.target.value)}
                value={selectedContextBundleId}
              >
                <option value="">Select a saved bundle</option>
                {contextBundles.map((contextBundle) => (
                  <option key={contextBundle.id} value={contextBundle.id}>
                    {contextBundle.name}
                  </option>
                ))}
              </select>
            </label>
          ) : null}

          {contextSource === "inline" ? (
            <>
              <label className="settings-field">
                <span>Inline context name</span>
                <input
                  aria-label="Inline context name"
                  name="inline_context_name"
                  onChange={(event) => setInlineContextName(event.target.value)}
                  value={inlineContextName}
                />
              </label>

              <label className="settings-field">
                <span>Inline context content</span>
                <textarea
                  aria-label="Inline context content"
                  name="inline_context_content"
                  onChange={(event) => setInlineContextContent(event.target.value)}
                  rows={6}
                  value={inlineContextContent}
                />
              </label>

              <label className="settings-field">
                <span>Inline context notes</span>
                <textarea
                  aria-label="Inline context notes"
                  name="inline_context_notes"
                  onChange={(event) => setInlineContextNotes(event.target.value)}
                  rows={3}
                  value={inlineContextNotes}
                />
              </label>
            </>
          ) : null}

          <p className="run-helper-copy">
            Config defaults keep historical runs stable, while saved-bundle and inline overrides are snapshotted for this launch only.
          </p>
        </div>
      </section>

      {latestRuns.length > 0 ? (
        <section className="shell-panel experiments-card">
          <div className="settings-card-header">
            <div>
              <p className="section-kicker">Latest launch</p>
              <h3>Immediate execution results</h3>
            </div>
            <p className="experiments-list-meta">
              Full run history, filters, and detail views land in the next backlog slices.
            </p>
          </div>

          <div className="run-result-grid">
            {latestRuns.map((run) => (
              <article className="experiment-card run-output-card" key={run.id}>
                <div className="experiment-card-header">
                  <div>
                    <p className="section-kicker">Run result</p>
                    <h3>
                      {run.config_snapshot.name} {run.config_snapshot.version_label}
                    </h3>
                  </div>
                  <span className={`run-status-pill run-status-pill-${run.status}`}>
                    {formatStatus(run.status)}
                  </span>
                </div>

                <dl className="experiment-metadata run-metrics">
                  <div>
                    <dt>Provider</dt>
                    <dd>
                      {formatProvider(run.provider)} / {run.model}
                    </dd>
                  </div>
                  <div>
                    <dt>Finished</dt>
                    <dd>{formatTimestamp(run.finished_at)}</dd>
                  </div>
                  <div>
                    <dt>Latency</dt>
                    <dd>{run.latency_ms === null ? "Unavailable" : `${run.latency_ms} ms`}</dd>
                  </div>
                  <div>
                    <dt>Estimated cost</dt>
                    <dd>{formatCurrency(run.estimated_cost_usd)}</dd>
                  </div>
                </dl>

                <dl className="experiment-metadata">
                  <div>
                    <dt>Rendered prompt</dt>
                    <dd>{run.config_snapshot.rendered_user_prompt}</dd>
                  </div>
                  <div>
                    <dt>Output</dt>
                    <dd>{run.output_text ?? "No output captured."}</dd>
                  </div>
                  <div>
                    <dt>Error</dt>
                    <dd>{run.error_message ?? "No execution error."}</dd>
                  </div>
                </dl>
              </article>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
