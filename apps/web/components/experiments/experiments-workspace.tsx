"use client";

import Link from "next/link";
import { startTransition, useState, type FormEvent } from "react";

import { useAppShellState } from "@/components/providers/app-shell-provider";
import { EmptyState } from "@/components/states/empty-state";
import { useApiClient } from "@/lib/api/browser";
import {
  ApiClientError,
  type CreateExperimentRequest,
  type ExperimentResponse,
} from "@/lib/api/client";

type ExperimentsWorkspaceProps = {
  initialExperiments: ExperimentResponse[];
};

type FeedbackState =
  | {
      tone: "error" | "success";
      message: string;
    }
  | null;

function normalizeOptionalText(value: string) {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
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

function sortExperiments(experiments: ExperimentResponse[]) {
  return [...experiments].sort((left, right) => {
    if (left.is_archived !== right.is_archived) {
      return Number(left.is_archived) - Number(right.is_archived);
    }

    const updatedComparison = right.updated_at.localeCompare(left.updated_at);
    if (updatedComparison !== 0) {
      return updatedComparison;
    }

    return left.name.localeCompare(right.name);
  });
}

function formatTimestamp(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function ExperimentsWorkspace({ initialExperiments }: ExperimentsWorkspaceProps) {
  const apiClient = useApiClient();
  const { clearGlobalError, setGlobalError, startLoading, stopLoading } = useAppShellState();

  const [experiments, setExperiments] = useState(() => sortExperiments(initialExperiments));
  const [feedback, setFeedback] = useState<FeedbackState>(null);
  const [activeAction, setActiveAction] = useState<string | null>(null);

  const [searchText, setSearchText] = useState("");
  const [tagText, setTagText] = useState("");
  const [includeArchived, setIncludeArchived] = useState(false);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [tags, setTags] = useState("");

  const archivedCount = experiments.filter((experiment) => experiment.is_archived).length;
  const activeCount = experiments.length - archivedCount;
  const discoveredTags = Array.from(new Set(experiments.flatMap((experiment) => experiment.tags)));

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

  function loadExperiments(options?: {
    search?: string;
    tagText?: string;
    includeArchived?: boolean;
  }) {
    const nextSearch = options?.search ?? searchText;
    const nextTagText = options?.tagText ?? tagText;
    const nextIncludeArchived = options?.includeArchived ?? includeArchived;

    return apiClient.experiments.list({
      search: normalizeOptionalText(nextSearch),
      tags: parseTags(nextTagText),
      includeArchived: nextIncludeArchived,
    });
  }

  function handleApplyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    void runTask({
      actionKey: "filter-experiments",
      errorTitle: "Could not refresh experiments",
      successMessage: "Experiment list refreshed.",
      work: () => loadExperiments(),
      commit: (nextExperiments) => {
        setExperiments(sortExperiments(nextExperiments));
      },
    });
  }

  function handleClearFilters() {
    const nextSearch = "";
    const nextTagText = "";
    const nextIncludeArchived = false;

    setSearchText(nextSearch);
    setTagText(nextTagText);
    setIncludeArchived(nextIncludeArchived);

    void runTask({
      actionKey: "clear-experiment-filters",
      errorTitle: "Could not clear experiment filters",
      successMessage: "Experiment filters cleared.",
      work: () =>
        loadExperiments({
          search: nextSearch,
          tagText: nextTagText,
          includeArchived: nextIncludeArchived,
        }),
      commit: (nextExperiments) => {
        setExperiments(sortExperiments(nextExperiments));
      },
    });
  }

  function handleQuickTag(tag: string) {
    setTagText(tag);

    void runTask({
      actionKey: `tag-${tag}`,
      errorTitle: "Could not filter experiments by tag",
      successMessage: `Showing experiments tagged "${tag}".`,
      work: () =>
        loadExperiments({
          tagText: tag,
        }),
      commit: (nextExperiments) => {
        setExperiments(sortExperiments(nextExperiments));
      },
    });
  }

  function handleCreateExperiment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const payload: CreateExperimentRequest = {
      name,
      description: normalizeOptionalText(description),
      tags: parseTags(tags),
    };

    void runTask({
      actionKey: "create-experiment",
      errorTitle: "Could not create experiment",
      successMessage: "Experiment created and added to the list.",
      work: async () => {
        await apiClient.experiments.create(payload);
        return apiClient.experiments.list();
      },
      commit: (nextExperiments) => {
        setExperiments(sortExperiments(nextExperiments));
        setName("");
        setDescription("");
        setTags("");
        setSearchText("");
        setTagText("");
        setIncludeArchived(false);
      },
    });
  }

  const filtersApplied = searchText.trim().length > 0 || tagText.trim().length > 0 || includeArchived;

  return (
    <div className="experiments-shell">
      <section className="three-column-grid experiments-summary-grid">
        <article className="shell-panel experiments-summary-card">
          <p className="section-kicker">Active experiments</p>
          <h2>{activeCount}</h2>
          <p className="status-copy">Current experiments ready for test cases, configs, and runs.</p>
        </article>

        <article className="shell-panel experiments-summary-card">
          <p className="section-kicker">Archived in view</p>
          <h2>{archivedCount}</h2>
          <p className="status-copy">
            {includeArchived
              ? "Archived work stays visible so older lanes remain discoverable."
              : "Archived experiments stay hidden until you explicitly include them."}
          </p>
        </article>

        <article className="shell-panel experiments-summary-card">
          <p className="section-kicker">Tag coverage</p>
          <h2>{discoveredTags.length}</h2>
          <p className="status-copy">Distinct tags visible in the current result set.</p>
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

      <section className="two-column-grid experiments-controls-grid">
        <article className="shell-panel experiments-card">
          <div className="settings-card-header">
            <div>
              <p className="section-kicker">Search and filter</p>
              <h2>Find the right experiment lane.</h2>
            </div>
          </div>

          <form className="settings-form" onSubmit={handleApplyFilters}>
            <fieldset className="settings-fieldset" disabled={activeAction === "filter-experiments"}>
              <div className="settings-field-grid">
                <label className="settings-field">
                  <span>Search by name</span>
                  <input
                    name="search"
                    onChange={(event) => setSearchText(event.target.value)}
                    placeholder="Support triage"
                    value={searchText}
                  />
                </label>

                <label className="settings-field">
                  <span>Tag filter</span>
                  <input
                    name="tag-filter"
                    onChange={(event) => setTagText(event.target.value)}
                    placeholder="support, triage"
                    value={tagText}
                  />
                </label>
              </div>

              <label className="experiments-checkbox">
                <input
                  checked={includeArchived}
                  onChange={(event) => setIncludeArchived(event.target.checked)}
                  type="checkbox"
                />
                <span>Include archived experiments in the list.</span>
              </label>
            </fieldset>

            <div className="settings-action-row">
              <button className="settings-primary-action" type="submit">
                Apply filters
              </button>
              <button className="settings-secondary-action" onClick={handleClearFilters} type="button">
                Clear filters
              </button>
            </div>
          </form>

          {discoveredTags.length > 0 ? (
            <div className="experiments-tag-row" aria-label="Visible tags">
              {discoveredTags.map((tag) => (
                <button
                  className="experiments-tag-pill"
                  key={tag}
                  onClick={() => handleQuickTag(tag)}
                  type="button"
                >
                  {tag}
                </button>
              ))}
            </div>
          ) : null}
        </article>

        <article className="shell-panel experiments-card experiments-card-accent">
          <div className="settings-card-header">
            <div>
              <p className="section-kicker">Create experiment</p>
              <h2>Start a fresh comparison lane.</h2>
            </div>
          </div>

          <form className="settings-form" onSubmit={handleCreateExperiment}>
            <fieldset className="settings-fieldset" disabled={activeAction === "create-experiment"}>
              <label className="settings-field">
                <span>Name</span>
                <input
                  name="name"
                  onChange={(event) => setName(event.target.value)}
                  placeholder="New experiment"
                  required
                  value={name}
                />
              </label>

              <label className="settings-field">
                <span>Description</span>
                <textarea
                  name="description"
                  onChange={(event) => setDescription(event.target.value)}
                  placeholder="Explain the task you are benchmarking."
                  rows={5}
                  value={description}
                />
              </label>

              <label className="settings-field">
                <span>Tags</span>
                <input
                  name="tags"
                  onChange={(event) => setTags(event.target.value)}
                  placeholder="support, prompt-iteration"
                  value={tags}
                />
              </label>
            </fieldset>

            <div className="settings-action-row">
              <button className="settings-primary-action" type="submit">
                Create experiment
              </button>
            </div>
          </form>
        </article>
      </section>

      <section className="shell-panel experiments-card">
        <div className="experiments-list-header">
          <div>
            <p className="section-kicker">Experiments index</p>
            <h2>Current experiment lanes</h2>
          </div>
          <p className="experiments-list-meta">
            {filtersApplied ? "Filtered results" : "All active experiments"}
          </p>
        </div>

        {experiments.length === 0 ? (
          <EmptyState
            action={
              filtersApplied ? (
                <button onClick={handleClearFilters} type="button">
                  Reset filters
                </button>
              ) : null
            }
            description={
              filtersApplied
                ? "The current search and tag filters returned no experiments. Reset them or create a new experiment."
                : "Create your first experiment to start organizing prompts, models, and future test cases."
            }
            label="Experiments"
            title={filtersApplied ? "No experiments match these filters" : "No experiments yet"}
          />
        ) : (
          <div className="experiments-card-grid">
            {experiments.map((experiment) => (
              <article className="experiment-card" key={experiment.id}>
                <div className="experiment-card-header">
                  <div>
                    <p className="section-kicker">{experiment.is_archived ? "Archived" : "Active"}</p>
                    <h3>{experiment.name}</h3>
                  </div>
                  <Link className="settings-secondary-action" href={`/experiments/${experiment.id}`}>
                    Open detail
                  </Link>
                </div>

                <p className="status-copy">
                  {experiment.description ?? "No description yet. Use the detail shell to define the intent and scope."}
                </p>

                <dl className="experiment-metadata">
                  <div>
                    <dt>Tags</dt>
                    <dd>{experiment.tags.length > 0 ? serializeTags(experiment.tags) : "No tags"}</dd>
                  </div>
                  <div>
                    <dt>Updated</dt>
                    <dd>{formatTimestamp(experiment.updated_at)}</dd>
                  </div>
                </dl>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
