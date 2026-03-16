"use client";

import Link from "next/link";
import { startTransition, useState } from "react";

import { useAppShellState } from "@/components/providers/app-shell-provider";
import { RunEvaluationEditor } from "@/components/runs/run-evaluation-editor";
import {
  formatDimensionScores,
  formatEvaluationNotes,
  formatEvaluationScore,
  formatEvaluationSignal,
} from "@/components/runs/run-evaluation-utils";
import { EmptyState } from "@/components/states/empty-state";
import { useApiClient } from "@/lib/api/browser";
import {
  ApiClientError,
  type RunDetailResponse,
  type RunHistoryResponse,
} from "@/lib/api/client";

type ExperimentCompareWorkspaceProps = {
  initialRuns: RunHistoryResponse[];
};

type FeedbackState =
  | {
      tone: "error" | "success";
      message: string;
    }
  | null;

type CompareGroup = {
  latestCreatedAt: string;
  runs: RunHistoryResponse[];
  testCaseId: string;
  testCaseInputPreview: string;
};

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

function formatTimestamp(value: string | null) {
  if (!value) {
    return "Unavailable";
  }

  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
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

function formatTags(tags: string[]) {
  return tags.length > 0 ? tags.join(", ") : "No tags";
}

function formatOptionalText(value: string | null) {
  return value && value.trim().length > 0 ? value : "Unavailable";
}

function groupRunsByTestCase(runs: RunHistoryResponse[]) {
  const groupedRuns = new Map<string, CompareGroup>();

  for (const run of runs) {
    const group = groupedRuns.get(run.test_case_id);
    if (group) {
      group.runs.push(run);
      if (run.created_at > group.latestCreatedAt) {
        group.latestCreatedAt = run.created_at;
      }
      continue;
    }

    groupedRuns.set(run.test_case_id, {
      latestCreatedAt: run.created_at,
      runs: [run],
      testCaseId: run.test_case_id,
      testCaseInputPreview: run.test_case_input_preview,
    });
  }

  return [...groupedRuns.values()]
    .filter((group) => group.runs.length >= 2)
    .map((group) => ({
      ...group,
      runs: [...group.runs].sort((left, right) => {
        const createdComparison = right.created_at.localeCompare(left.created_at);
        if (createdComparison !== 0) {
          return createdComparison;
        }

        return left.id.localeCompare(right.id);
      }),
    }))
    .sort((left, right) => right.latestCreatedAt.localeCompare(left.latestCreatedAt));
}

export function ExperimentCompareWorkspace({
  initialRuns,
}: ExperimentCompareWorkspaceProps) {
  const apiClient = useApiClient();
  const { clearGlobalError, setGlobalError, startLoading, stopLoading } = useAppShellState();
  const [runs, setRuns] = useState(initialRuns);
  const compareGroups = groupRunsByTestCase(runs);
  const [selectedTestCaseId, setSelectedTestCaseId] = useState<string | null>(
    compareGroups[0]?.testCaseId ?? null,
  );
  const [selectedRunIds, setSelectedRunIds] = useState<Set<string>>(() => new Set());
  const [comparedRuns, setComparedRuns] = useState<RunDetailResponse[]>([]);
  const [activeAction, setActiveAction] = useState<"load-compare" | null>(null);
  const [feedback, setFeedback] = useState<FeedbackState>(null);

  const activeGroup =
    compareGroups.find((group) => group.testCaseId === selectedTestCaseId) ?? compareGroups[0] ?? null;
  const selectedRuns = activeGroup
    ? activeGroup.runs.filter((run) => selectedRunIds.has(run.id))
    : [];
  const firstComparedRun = comparedRuns[0] ?? null;

  function handleEvaluationChange(runId: string, evaluation: RunDetailResponse["evaluation"]) {
    startTransition(() => {
      setComparedRuns((current) =>
        current.map((run) => (run.id === runId ? { ...run, evaluation } : run)),
      );
      setRuns((current) =>
        current.map((run) => (run.id === runId ? { ...run, evaluation } : run)),
      );
    });
  }

  function handleSelectTestCase(testCaseId: string) {
    setFeedback(null);
    startTransition(() => {
      setSelectedTestCaseId(testCaseId);
      setSelectedRunIds(new Set());
      setComparedRuns([]);
    });
  }

  function handleToggleRun(runId: string) {
    let exceededLimit = false;

    setSelectedRunIds((current) => {
      const nextSelectedRunIds = new Set(current);

      if (nextSelectedRunIds.has(runId)) {
        nextSelectedRunIds.delete(runId);
        return nextSelectedRunIds;
      }

      if (nextSelectedRunIds.size >= 4) {
        exceededLimit = true;
        return current;
      }

      nextSelectedRunIds.add(runId);
      return nextSelectedRunIds;
    });

    if (exceededLimit) {
      setFeedback({
        tone: "error",
        message: "Choose up to four runs for one compare view.",
      });
      return;
    }

    setFeedback(null);
    startTransition(() => {
      setComparedRuns([]);
    });
  }

  async function handleLoadCompare() {
    if (selectedRuns.length < 2 || selectedRuns.length > 4) {
      setFeedback({
        tone: "error",
        message: "Select between two and four runs from one test case.",
      });
      return;
    }

    clearGlobalError();
    setFeedback(null);
    setActiveAction("load-compare");
    startLoading();

    try {
      const nextComparedRuns = await Promise.all(
        selectedRuns.map((run) => apiClient.runs.get(run.id)),
      );
      const distinctTestCaseIds = new Set(nextComparedRuns.map((run) => run.test_case_id));

      if (distinctTestCaseIds.size !== 1) {
        throw new Error("Selected runs no longer share one test case.");
      }

      startTransition(() => {
        setComparedRuns(nextComparedRuns);
        setFeedback({
          tone: "success",
          message: `Loaded ${nextComparedRuns.length} runs side by side.`,
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
        title: "Could not load compare view",
        detail,
      });
    } finally {
      stopLoading();
      setActiveAction(null);
    }
  }

  if (compareGroups.length === 0) {
    return (
      <div className="experiment-compare-layout" role="tabpanel">
        <EmptyState
          description="Launch at least two runs against the same test case before trying to compare outputs side by side."
          label="Compare"
          title="No compare-ready runs yet"
        />
      </div>
    );
  }

  return (
    <div className="experiment-compare-layout" role="tabpanel">
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
          <p className="section-kicker">Compare-ready cases</p>
          <h3>{compareGroups.length}</h3>
          <p className="status-copy">Each option already has at least two runs tied to one test case.</p>
        </article>

        <article className="shell-panel experiments-summary-card">
          <p className="section-kicker">Runs in scope</p>
          <h3>{runs.length}</h3>
          <p className="status-copy">The compare tab only uses runs already owned by the signed-in user.</p>
        </article>

        <article className="shell-panel experiments-summary-card">
          <p className="section-kicker">Selection target</p>
          <h3>{selectedRuns.length}/4</h3>
          <p className="status-copy">Pick two to four runs before loading the side-by-side view.</p>
        </article>
      </section>

      <section className="two-column-grid experiments-controls-grid">
        <article className="shell-panel experiments-card experiments-card-accent compare-selection-card">
          <div className="settings-card-header">
            <div>
              <p className="section-kicker">Compare selection</p>
              <h3>Choose one test case, then pick the runs you want to judge together.</h3>
            </div>
            <p className="experiments-list-meta">
              This workflow reuses the run history and run detail APIs instead of introducing a second read model.
            </p>
          </div>

          <label className="settings-field">
            <span>Test case</span>
            <select
              aria-label="Compare test case"
              onChange={(event) => handleSelectTestCase(event.target.value)}
              value={activeGroup?.testCaseId ?? ""}
            >
              {compareGroups.map((group) => (
                <option key={group.testCaseId} value={group.testCaseId}>
                  {group.testCaseInputPreview}
                </option>
              ))}
            </select>
          </label>

          <p className="run-helper-copy">
            {activeGroup?.runs.length ?? 0} runs are available for this test case. The newest run appears first.
          </p>

          <div className="compare-run-list" role="group" aria-label="Compare run selection">
            {activeGroup?.runs.map((run) => {
              const isSelected = selectedRunIds.has(run.id);
              const disableUncheckedSelection = !isSelected && selectedRunIds.size >= 4;

              return (
                <label className="compare-run-card" key={run.id}>
                  <input
                    aria-label={`Select run ${run.config_name} ${run.config_version_label}`}
                    checked={isSelected}
                    disabled={disableUncheckedSelection}
                    onChange={() => handleToggleRun(run.id)}
                    type="checkbox"
                  />
                  <div className="compare-run-card-body">
                    <div className="compare-run-card-header">
                      <div>
                        <h4>
                          {run.config_name} {run.config_version_label}
                        </h4>
                        <p>
                          {formatProvider(run.provider)} / {run.model}
                        </p>
                      </div>
                      <span className={`run-status-pill run-status-pill-${run.status}`}>
                        {formatStatus(run.status)}
                      </span>
                    </div>

                    <dl className="compare-run-meta-grid">
                      <div>
                        <dt>Created</dt>
                        <dd>{formatTimestamp(run.created_at)}</dd>
                      </div>
                      <div>
                        <dt>Latency</dt>
                        <dd>{run.latency_ms === null ? "Unavailable" : `${run.latency_ms} ms`}</dd>
                      </div>
                      <div>
                        <dt>Cost</dt>
                        <dd>{formatCurrency(run.estimated_cost_usd)}</dd>
                      </div>
                      <div>
                        <dt>Score</dt>
                        <dd>{formatEvaluationScore(run.evaluation)}</dd>
                      </div>
                      <div>
                        <dt>Tags</dt>
                        <dd>{formatTags(run.tags)}</dd>
                      </div>
                      <div>
                        <dt>Notes</dt>
                        <dd>{formatEvaluationNotes(run.evaluation)}</dd>
                      </div>
                    </dl>
                  </div>
                </label>
              );
            })}
          </div>

          <div className="run-launch-action-row">
            <p className="run-helper-copy">
              {selectedRuns.length < 2
                ? "Choose at least two runs to continue."
                : "Selection is ready for side-by-side comparison."}
            </p>
            <button
              className="cta-link secondary"
              disabled={activeAction === "load-compare" || selectedRuns.length < 2}
              onClick={handleLoadCompare}
              type="button"
            >
              {activeAction === "load-compare" ? "Loading compare view..." : "Load compare view"}
            </button>
          </div>
        </article>

        <article className="shell-panel experiments-card compare-selection-card">
          <div className="settings-card-header">
            <div>
              <p className="section-kicker">Shared test case</p>
              <h3>Keep the shared input visible while you read each output side by side.</h3>
            </div>
          </div>

          <dl className="run-detail-meta-grid">
            <div>
              <dt>Input preview</dt>
              <dd>{activeGroup?.testCaseInputPreview ?? "Unavailable"}</dd>
            </div>
            <div>
              <dt>Selected runs</dt>
              <dd>{selectedRuns.length}</dd>
            </div>
            <div>
              <dt>Expected output</dt>
              <dd>{formatOptionalText(firstComparedRun?.input_snapshot.expected_output_text ?? null)}</dd>
            </div>
            <div>
              <dt>Test case notes</dt>
              <dd>{formatOptionalText(firstComparedRun?.input_snapshot.notes ?? null)}</dd>
            </div>
            <div>
              <dt>Test case tags</dt>
              <dd>{formatTags(firstComparedRun?.input_snapshot.tags ?? [])}</dd>
            </div>
            <div>
              <dt>Workflow mode</dt>
              <dd>{firstComparedRun?.workflow_mode ?? "Compare selection not loaded yet"}</dd>
            </div>
          </dl>

          <p className="run-helper-copy">
            Load the compare view to inspect the full prompt snapshot, context, output, and failure state for each selected run.
          </p>
        </article>
      </section>

      {comparedRuns.length > 0 ? (
        <section className="compare-results-shell">
          <div className="settings-card-header">
            <div>
              <p className="section-kicker">Side-by-side compare</p>
              <h2>Read the shared input once, then judge each run against the same snapshot.</h2>
            </div>
            <p className="experiments-list-meta">
              Save manual evaluation directly on each compared run without leaving the workflow.
            </p>
          </div>

          <article className="shell-panel compare-shared-input-card">
            <div className="compare-section-header">
              <h3>Shared input snapshot</h3>
              <p>The compared runs all point at this same test case record.</p>
            </div>

            <div className="compare-copy-grid">
              <section>
                <h4>Input</h4>
                <pre>{firstComparedRun?.input_snapshot.input_text ?? "Unavailable"}</pre>
              </section>

              <section>
                <h4>Expected output</h4>
                <pre>{formatOptionalText(firstComparedRun?.input_snapshot.expected_output_text ?? null)}</pre>
              </section>
            </div>
          </article>

          <div className="compare-results-grid">
            {comparedRuns.map((run) => (
              <article className="shell-panel compare-run-detail-card" key={run.id}>
                <div className="compare-run-detail-header">
                  <div>
                    <p className="section-kicker">{run.config_snapshot.version_label}</p>
                    <h3>{run.config_snapshot.name}</h3>
                    <p className="run-helper-copy">
                      {formatProvider(run.provider)} / {run.model}
                    </p>
                  </div>
                  <span className={`run-status-pill run-status-pill-${run.status}`}>
                    {formatStatus(run.status)}
                  </span>
                </div>

                <dl className="compare-run-meta-grid">
                  <div>
                    <dt>Created</dt>
                    <dd>{formatTimestamp(run.created_at)}</dd>
                  </div>
                  <div>
                    <dt>Finished</dt>
                    <dd>{formatTimestamp(run.finished_at)}</dd>
                  </div>
                  <div>
                    <dt>Workflow</dt>
                    <dd>{run.workflow_mode}</dd>
                  </div>
                  <div>
                    <dt>Latency</dt>
                    <dd>{run.latency_ms === null ? "Unavailable" : `${run.latency_ms} ms`}</dd>
                  </div>
                  <div>
                    <dt>Cost</dt>
                    <dd>{formatCurrency(run.estimated_cost_usd)}</dd>
                  </div>
                  <div>
                    <dt>Score</dt>
                    <dd>{formatEvaluationScore(run.evaluation)}</dd>
                  </div>
                  <div>
                    <dt>Tags</dt>
                    <dd>{formatTags(run.config_snapshot.tags)}</dd>
                  </div>
                  <div>
                    <dt>Signal</dt>
                    <dd>{formatEvaluationSignal(run.evaluation)}</dd>
                  </div>
                </dl>

                <div className="compare-section">
                  <div className="compare-section-header">
                    <h4>Output</h4>
                    <Link
                      aria-label={`Open ${run.config_snapshot.name} detail`}
                      className="cta-link secondary"
                      href={`/runs/${run.id}`}
                    >
                      Open detail
                    </Link>
                  </div>
                  <pre>{run.output_text ?? formatOptionalText(run.error_message)}</pre>
                </div>

                <div className="compare-section">
                  <div className="compare-section-header">
                    <h4>Rendered prompts</h4>
                    <p>Immutable prompt text captured at execution time.</p>
                  </div>

                  <div className="compare-copy-grid">
                    <section>
                      <h5>System</h5>
                      <pre>{formatOptionalText(run.config_snapshot.rendered_system_prompt)}</pre>
                    </section>
                    <section>
                      <h5>User</h5>
                      <pre>{run.config_snapshot.rendered_user_prompt}</pre>
                    </section>
                  </div>
                </div>

                <div className="compare-section">
                  <div className="compare-section-header">
                    <h4>Snapshot context</h4>
                    <p>Provider and context metadata used for this exact execution.</p>
                  </div>

                  <dl className="compare-run-meta-grid">
                    <div>
                      <dt>Provider</dt>
                      <dd>{formatProvider(run.config_snapshot.provider)}</dd>
                    </div>
                    <div>
                      <dt>Model</dt>
                      <dd>{run.config_snapshot.model}</dd>
                    </div>
                    <div>
                      <dt>Temperature</dt>
                      <dd>{run.config_snapshot.temperature}</dd>
                    </div>
                    <div>
                      <dt>Max output tokens</dt>
                      <dd>{run.config_snapshot.max_output_tokens}</dd>
                    </div>
                  </dl>

                  {run.context_snapshot ? (
                    <pre>{run.context_snapshot.content_text}</pre>
                  ) : (
                    <p className="run-helper-copy">No additional context snapshot was stored for this run.</p>
                  )}
                </div>

                <RunEvaluationEditor
                  initialEvaluation={run.evaluation}
                  onChange={(evaluation) => handleEvaluationChange(run.id, evaluation)}
                  runId={run.id}
                />
              </article>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
