import { type RunDetailResponse } from "@/lib/api/client";

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

type RunDetailProps = {
  run: RunDetailResponse;
};

export function RunDetail({ run }: RunDetailProps) {
  return (
    <div className="run-detail-shell">
      <section className="three-column-grid runs-summary-grid">
        <article className="shell-panel runs-summary-card">
          <p className="section-kicker">Run status</p>
          <h3>{formatStatus(run.status)}</h3>
          <p className="status-copy">
            {run.experiment_name ?? "Deleted experiment"} via {formatProvider(run.provider)}
          </p>
        </article>

        <article className="shell-panel runs-summary-card">
          <p className="section-kicker">Latency</p>
          <h3>{run.latency_ms === null ? "Unavailable" : `${run.latency_ms} ms`}</h3>
          <p className="status-copy">Recorded from the provider response for this immutable run.</p>
        </article>

        <article className="shell-panel runs-summary-card">
          <p className="section-kicker">Estimated cost</p>
          <h3>{formatCurrency(run.estimated_cost_usd)}</h3>
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
          </div>

          <dl className="run-detail-meta-grid">
            <div>
              <dt>Experiment</dt>
              <dd>{run.experiment_name ?? "Deleted experiment"}</dd>
            </div>
            <div>
              <dt>Workflow mode</dt>
              <dd>{run.workflow_mode}</dd>
            </div>
            <div>
              <dt>Provider model</dt>
              <dd>
                {formatProvider(run.provider)} / {run.model}
              </dd>
            </div>
            <div>
              <dt>Config snapshot</dt>
              <dd>
                {run.config_snapshot.name} {run.config_snapshot.version_label}
              </dd>
            </div>
            <div>
              <dt>Created</dt>
              <dd>{formatTimestamp(run.created_at)}</dd>
            </div>
            <div>
              <dt>Finished</dt>
              <dd>{formatTimestamp(run.finished_at)}</dd>
            </div>
            <div>
              <dt>Run id</dt>
              <dd>{run.id}</dd>
            </div>
            <div>
              <dt>Test case snapshot</dt>
              <dd>{run.input_snapshot.test_case_id}</dd>
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
              <dd>{run.usage_input_tokens ?? "Unavailable"}</dd>
            </div>
            <div>
              <dt>Output tokens</dt>
              <dd>{run.usage_output_tokens ?? "Unavailable"}</dd>
            </div>
            <div>
              <dt>Total tokens</dt>
              <dd>{run.usage_total_tokens ?? "Unavailable"}</dd>
            </div>
            <div>
              <dt>Credential id</dt>
              <dd>{run.credential_id ?? "Not stored"}</dd>
            </div>
            <div>
              <dt>Started</dt>
              <dd>{formatTimestamp(run.started_at)}</dd>
            </div>
            <div>
              <dt>Updated</dt>
              <dd>{formatTimestamp(run.updated_at)}</dd>
            </div>
          </dl>
        </article>
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
              <pre className="run-detail-block">{formatPrompt(run.config_snapshot.system_prompt_template)}</pre>
            </div>
            <div className="run-detail-block-shell">
              <p className="run-detail-block-label">Rendered system prompt</p>
              <pre className="run-detail-block">{formatPrompt(run.config_snapshot.rendered_system_prompt)}</pre>
            </div>
            <div className="run-detail-block-shell">
              <p className="run-detail-block-label">User prompt template</p>
              <pre className="run-detail-block">{run.config_snapshot.user_prompt_template}</pre>
            </div>
            <div className="run-detail-block-shell">
              <p className="run-detail-block-label">Rendered user prompt</p>
              <pre className="run-detail-block">{run.config_snapshot.rendered_user_prompt}</pre>
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
              <pre className="run-detail-block">{run.input_snapshot.input_text}</pre>
            </div>
            <div className="run-detail-meta-grid">
              <div>
                <dt>Expected output</dt>
                <dd>{run.input_snapshot.expected_output_text ?? "Not provided"}</dd>
              </div>
              <div>
                <dt>Input tags</dt>
                <dd>{formatTags(run.input_snapshot.tags)}</dd>
              </div>
              <div>
                <dt>Notes</dt>
                <dd>{run.input_snapshot.notes ?? "Not provided"}</dd>
              </div>
              <div>
                <dt>Config tags</dt>
                <dd>{formatTags(run.config_snapshot.tags)}</dd>
              </div>
            </div>
            <div className="run-detail-block-shell">
              <p className="run-detail-block-label">Context snapshot</p>
              <pre className="run-detail-block">
                {run.context_snapshot
                  ? `${run.context_snapshot.name ?? "Unnamed context"}\n\n${run.context_snapshot.content_text}`
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
          {run.output_text ? (
            <div className="run-detail-block-shell">
              <p className="run-detail-block-label">Output text</p>
              <pre className="run-detail-block">{run.output_text}</pre>
            </div>
          ) : null}

          <div className="run-detail-block-shell">
            <p className="run-detail-block-label">Failure state</p>
            <pre
              className={`run-detail-block${run.error_message ? " run-detail-block-error" : ""}`}
            >
              {run.error_message ?? "No failure was recorded for this run."}
            </pre>
          </div>
        </div>
      </section>
    </div>
  );
}
