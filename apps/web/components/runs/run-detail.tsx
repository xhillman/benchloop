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
import { useApiClient } from "@/lib/api/browser";
import { ApiClientError, type RunDetailResponse, type RunResponse } from "@/lib/api/client";

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

function formatPrompt(value: string | null) {
  return value && value.trim().length > 0 ? value : "Not used for this run.";
}

type FeedbackState =
  | {
      message: string;
      tone: "error" | "success";
    }
  | null;

type RunDetailProps = {
  run: RunDetailResponse;
};

export function RunDetail({ run }: RunDetailProps) {
  const apiClient = useApiClient();
  const { clearGlobalError, setGlobalError, startLoading, stopLoading } = useAppShellState();
  const [runDetail, setRunDetail] = useState(run);
  const [activeAction, setActiveAction] = useState<"rerun" | null>(null);
  const [feedback, setFeedback] = useState<FeedbackState>(null);
  const [latestRerun, setLatestRerun] = useState<RunResponse | null>(null);

  async function handleRerun() {
    clearGlobalError();
    setFeedback(null);
    setActiveAction("rerun");
    startLoading();

    try {
      const rerun = await apiClient.runs.rerun(runDetail.id);

      startTransition(() => {
        setLatestRerun(rerun);
        setFeedback({
          tone: "success",
          message: "Rerun created from the stored snapshot.",
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
        title: "Could not rerun this snapshot",
        detail,
      });
    } finally {
      stopLoading();
      setActiveAction(null);
    }
  }

  return (
    <div className="run-detail-shell">
      {feedback ? (
        <div
          className={`settings-feedback settings-feedback-${feedback.tone}`}
          role={feedback.tone === "error" ? "alert" : "status"}
        >
          {feedback.message}
        </div>
      ) : null}

      {latestRerun ? (
        <section className="shell-panel runs-card runs-card-accent">
          <div className="settings-card-header">
            <div>
              <p className="section-kicker">Snapshot rerun</p>
              <h2>The new run keeps the original prompt and input snapshot intact.</h2>
            </div>
            <p className="experiments-list-meta">
              Later config or test case edits are ignored for this rerun path.
            </p>
          </div>

          <dl className="run-detail-meta-grid">
            <div>
              <dt>New run id</dt>
              <dd>{latestRerun.id}</dd>
            </div>
            <div>
              <dt>Status</dt>
              <dd>{formatStatus(latestRerun.status)}</dd>
            </div>
            <div>
              <dt>Provider model</dt>
              <dd>
                {formatProvider(latestRerun.provider)} / {latestRerun.model}
              </dd>
            </div>
            <div>
              <dt>Created</dt>
              <dd>{formatTimestamp(latestRerun.created_at)}</dd>
            </div>
          </dl>

          <div className="cta-row">
            <Link className="cta-link secondary" href={`/runs/${latestRerun.id}`}>
              Open rerun
            </Link>
          </div>
        </section>
      ) : null}

      <section className="three-column-grid runs-summary-grid">
        <article className="shell-panel runs-summary-card">
          <p className="section-kicker">Run status</p>
          <h3>{formatStatus(runDetail.status)}</h3>
          <p className="status-copy">
            {runDetail.experiment_name ?? "Deleted experiment"} via {formatProvider(runDetail.provider)}
          </p>
        </article>

        <article className="shell-panel runs-summary-card">
          <p className="section-kicker">Latency</p>
          <h3>{runDetail.latency_ms === null ? "Unavailable" : `${runDetail.latency_ms} ms`}</h3>
          <p className="status-copy">Recorded from the provider response for this immutable run.</p>
        </article>

        <article className="shell-panel runs-summary-card">
          <p className="section-kicker">Estimated cost</p>
          <h3>{formatCurrency(runDetail.estimated_cost_usd)}</h3>
          <p className="status-copy">Stored with the run so later config edits cannot rewrite history.</p>
        </article>
      </section>

      <section className="two-column-grid">
        <article className="shell-panel runs-card runs-card-accent">
          <div className="settings-card-header">
            <div>
              <p className="section-kicker">Run identity</p>
              <h2>Source-of-truth metadata for this execution record.</h2>
            </div>
            <button
              className="cta-link secondary"
              disabled={activeAction === "rerun"}
              onClick={handleRerun}
              type="button"
            >
              {activeAction === "rerun" ? "Rerunning snapshot..." : "Rerun from snapshot"}
            </button>
          </div>

          <dl className="run-detail-meta-grid">
            <div>
              <dt>Experiment</dt>
              <dd>{runDetail.experiment_name ?? "Deleted experiment"}</dd>
            </div>
            <div>
              <dt>Workflow mode</dt>
              <dd>{runDetail.workflow_mode}</dd>
            </div>
            <div>
              <dt>Provider model</dt>
              <dd>
                {formatProvider(runDetail.provider)} / {runDetail.model}
              </dd>
            </div>
            <div>
              <dt>Config snapshot</dt>
              <dd>
                {runDetail.config_snapshot.name} {runDetail.config_snapshot.version_label}
              </dd>
            </div>
            <div>
              <dt>Created</dt>
              <dd>{formatTimestamp(runDetail.created_at)}</dd>
            </div>
            <div>
              <dt>Finished</dt>
              <dd>{formatTimestamp(runDetail.finished_at)}</dd>
            </div>
            <div>
              <dt>Run id</dt>
              <dd>{runDetail.id}</dd>
            </div>
            <div>
              <dt>Test case snapshot</dt>
              <dd>{runDetail.input_snapshot.test_case_id}</dd>
            </div>
          </dl>
        </article>

        <article className="shell-panel runs-card">
          <div className="settings-card-header">
            <div>
              <p className="section-kicker">Usage</p>
              <h2>Token, timing, and cost telemetry captured at execution time.</h2>
            </div>
          </div>

          <dl className="run-detail-meta-grid">
            <div>
              <dt>Input tokens</dt>
              <dd>{runDetail.usage_input_tokens ?? "Unavailable"}</dd>
            </div>
            <div>
              <dt>Output tokens</dt>
              <dd>{runDetail.usage_output_tokens ?? "Unavailable"}</dd>
            </div>
            <div>
              <dt>Total tokens</dt>
              <dd>{runDetail.usage_total_tokens ?? "Unavailable"}</dd>
            </div>
            <div>
              <dt>Credential id</dt>
              <dd>{runDetail.credential_id ?? "Not stored"}</dd>
            </div>
            <div>
              <dt>Started</dt>
              <dd>{formatTimestamp(runDetail.started_at)}</dd>
            </div>
            <div>
              <dt>Updated</dt>
              <dd>{formatTimestamp(runDetail.updated_at)}</dd>
            </div>
          </dl>
        </article>
      </section>

      <section className="two-column-grid">
        <article className="shell-panel runs-card">
          <div className="settings-card-header">
            <div>
              <p className="section-kicker">Evaluation snapshot</p>
              <h2>Manual judgment stored with this run.</h2>
            </div>
          </div>

          <dl className="run-detail-meta-grid">
            <div>
              <dt>Overall score</dt>
              <dd>{formatEvaluationScore(runDetail.evaluation)}</dd>
            </div>
            <div>
              <dt>Signal</dt>
              <dd>{formatEvaluationSignal(runDetail.evaluation)}</dd>
            </div>
            <div>
              <dt>Dimensions</dt>
              <dd>{formatDimensionScores(runDetail.evaluation)}</dd>
            </div>
            <div>
              <dt>Notes</dt>
              <dd>{formatEvaluationNotes(runDetail.evaluation)}</dd>
            </div>
          </dl>
        </article>

        <RunEvaluationEditor
          initialEvaluation={runDetail.evaluation}
          onChange={(evaluation) => {
            startTransition(() => {
              setRunDetail((current) => ({
                ...current,
                evaluation,
              }));
            });
          }}
          runId={runDetail.id}
        />
      </section>

      <section className="two-column-grid">
        <article className="shell-panel runs-card">
          <div className="settings-card-header">
            <div>
              <p className="section-kicker">Prompt snapshot</p>
              <h2>Templates and rendered prompts exactly as they were sent.</h2>
            </div>
          </div>

          <div className="run-detail-stack">
            <div className="run-detail-block-shell">
              <p className="run-detail-block-label">System prompt template</p>
              <pre className="run-detail-block">{formatPrompt(runDetail.config_snapshot.system_prompt_template)}</pre>
            </div>
            <div className="run-detail-block-shell">
              <p className="run-detail-block-label">Rendered system prompt</p>
              <pre className="run-detail-block">
                {formatPrompt(runDetail.config_snapshot.rendered_system_prompt)}
              </pre>
            </div>
            <div className="run-detail-block-shell">
              <p className="run-detail-block-label">User prompt template</p>
              <pre className="run-detail-block">{runDetail.config_snapshot.user_prompt_template}</pre>
            </div>
            <div className="run-detail-block-shell">
              <p className="run-detail-block-label">Rendered user prompt</p>
              <pre className="run-detail-block">{runDetail.config_snapshot.rendered_user_prompt}</pre>
            </div>
          </div>
        </article>

        <article className="shell-panel runs-card">
          <div className="settings-card-header">
            <div>
              <p className="section-kicker">Input and context</p>
              <h2>Immutable test case content and any attached execution context.</h2>
            </div>
          </div>

          <div className="run-detail-stack">
            <div className="run-detail-block-shell">
              <p className="run-detail-block-label">Input text</p>
              <pre className="run-detail-block">{runDetail.input_snapshot.input_text}</pre>
            </div>
            <div className="run-detail-meta-grid">
              <div>
                <dt>Expected output</dt>
                <dd>{runDetail.input_snapshot.expected_output_text ?? "Not provided"}</dd>
              </div>
              <div>
                <dt>Input tags</dt>
                <dd>{formatTags(runDetail.input_snapshot.tags)}</dd>
              </div>
              <div>
                <dt>Notes</dt>
                <dd>{runDetail.input_snapshot.notes ?? "Not provided"}</dd>
              </div>
              <div>
                <dt>Config tags</dt>
                <dd>{formatTags(runDetail.config_snapshot.tags)}</dd>
              </div>
            </div>
            <div className="run-detail-block-shell">
              <p className="run-detail-block-label">Context snapshot</p>
              <pre className="run-detail-block">
                {runDetail.context_snapshot
                  ? `${runDetail.context_snapshot.name ?? "Unnamed context"}\n\n${runDetail.context_snapshot.content_text}`
                  : "No context snapshot was attached to this run."}
              </pre>
            </div>
          </div>
        </article>
      </section>

      <section className="shell-panel runs-card">
        <div className="settings-card-header">
          <div>
            <p className="section-kicker">Execution result</p>
            <h2>Output text or failure state preserved exactly as recorded.</h2>
          </div>
        </div>

        <div className="run-detail-stack">
          {runDetail.output_text ? (
            <div className="run-detail-block-shell">
              <p className="run-detail-block-label">Output text</p>
              <pre className="run-detail-block">{runDetail.output_text}</pre>
            </div>
          ) : null}

          <div className="run-detail-block-shell">
            <p className="run-detail-block-label">Failure state</p>
            <pre
              className={`run-detail-block${runDetail.error_message ? " run-detail-block-error" : ""}`}
            >
              {runDetail.error_message ?? "No failure was recorded for this run."}
            </pre>
          </div>
        </div>
      </section>
    </div>
  );
}
