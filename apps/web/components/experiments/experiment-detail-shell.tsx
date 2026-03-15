"use client";

import { useRouter } from "next/navigation";
import { startTransition, useState, type FormEvent } from "react";

import { useAppShellState } from "@/components/providers/app-shell-provider";
import { useApiClient } from "@/lib/api/browser";
import {
  ApiClientError,
  type ExperimentResponse,
  type UpdateExperimentRequest,
} from "@/lib/api/client";

type ExperimentDetailShellProps = {
  initialExperiment: ExperimentResponse;
};

type DetailTab = "compare" | "configs" | "overview" | "runs" | "test-cases";

type FeedbackState =
  | {
      tone: "error" | "success";
      message: string;
    }
  | null;

const tabCopy: Record<
  Exclude<DetailTab, "overview">,
  {
    heading: string;
    description: string;
  }
> = {
  "test-cases": {
    heading: "Test case tab placeholder",
    description: "B021 will attach experiment-scoped test case CRUD and duplication here.",
  },
  configs: {
    heading: "Config tab placeholder",
    description: "B022 will add prompt and model config editing inside this experiment lane.",
  },
  runs: {
    heading: "Runs tab placeholder",
    description: "Later execution work will turn this lane into the run history surface for the experiment.",
  },
  compare: {
    heading: "Compare tab placeholder",
    description: "Manual compare and evaluation will land here once run outputs exist to judge side by side.",
  },
};

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

function formatTimestamp(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

const tabs: { value: DetailTab; label: string }[] = [
  { value: "overview", label: "Overview" },
  { value: "test-cases", label: "Test cases" },
  { value: "configs", label: "Configs" },
  { value: "runs", label: "Runs" },
  { value: "compare", label: "Compare" },
];

export function ExperimentDetailShell({ initialExperiment }: ExperimentDetailShellProps) {
  const apiClient = useApiClient();
  const router = useRouter();
  const { clearGlobalError, setGlobalError, startLoading, stopLoading } = useAppShellState();

  const [experiment, setExperiment] = useState(initialExperiment);
  const [activeTab, setActiveTab] = useState<DetailTab>("overview");
  const [feedback, setFeedback] = useState<FeedbackState>(null);
  const [activeAction, setActiveAction] = useState<string | null>(null);

  const [name, setName] = useState(initialExperiment.name);
  const [description, setDescription] = useState(initialExperiment.description ?? "");
  const [tags, setTags] = useState(serializeTags(initialExperiment.tags));
  const [isArchived, setIsArchived] = useState(initialExperiment.is_archived);

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

  function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const payload: UpdateExperimentRequest = {
      name,
      description: normalizeOptionalText(description),
      tags: parseTags(tags),
      is_archived: isArchived,
    };

    void runTask({
      actionKey: "save-experiment",
      errorTitle: "Could not save experiment",
      successMessage: "Experiment updated.",
      work: () => apiClient.experiments.update(experiment.id, payload),
      commit: (nextExperiment) => {
        setExperiment(nextExperiment);
        setName(nextExperiment.name);
        setDescription(nextExperiment.description ?? "");
        setTags(serializeTags(nextExperiment.tags));
        setIsArchived(nextExperiment.is_archived);
      },
    });
  }

  function handleDelete() {
    void runTask({
      actionKey: "delete-experiment",
      errorTitle: "Could not delete experiment",
      successMessage: "Experiment deleted.",
      work: async () => {
        await apiClient.experiments.delete(experiment.id);
      },
      commit: () => {
        router.push("/experiments");
      },
    });
  }

  const archivedLabel = experiment.is_archived ? "Archived" : "Active";

  return (
    <div className="experiments-shell">
      <section className="three-column-grid experiments-summary-grid">
        <article className="shell-panel experiments-summary-card">
          <p className="section-kicker">Experiment status</p>
          <h2>{archivedLabel}</h2>
          <p className="status-copy">This experiment is ready to host the next backlog slices.</p>
        </article>

        <article className="shell-panel experiments-summary-card">
          <p className="section-kicker">Tag set</p>
          <h2>{experiment.tags.length}</h2>
          <p className="status-copy">
            {experiment.tags.length > 0 ? serializeTags(experiment.tags) : "No tags applied yet."}
          </p>
        </article>

        <article className="shell-panel experiments-summary-card">
          <p className="section-kicker">Last updated</p>
          <h2>{formatTimestamp(experiment.updated_at)}</h2>
          <p className="status-copy">Changes here stay scoped to the owning user only.</p>
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

      <section className="shell-panel experiments-card">
        <div className="experiments-list-header">
          <div>
            <p className="section-kicker">Experiment shell</p>
            <h2>{experiment.name}</h2>
          </div>
          <p className="experiments-list-meta">{archivedLabel}</p>
        </div>

        <div aria-label="Experiment detail tabs" className="experiment-tabs" role="tablist">
          {tabs.map((tab) => (
            <button
              aria-selected={activeTab === tab.value}
              className={`experiment-tab ${activeTab === tab.value ? "experiment-tab-active" : ""}`}
              key={tab.value}
              onClick={() => setActiveTab(tab.value)}
              role="tab"
              type="button"
            >
              {tab.label}
            </button>
          ))}
        </div>

        {activeTab === "overview" ? (
          <form className="settings-form" onSubmit={handleSave}>
            <fieldset className="settings-fieldset" disabled={activeAction === "save-experiment"}>
              <div className="settings-field-grid">
                <label className="settings-field">
                  <span>Name</span>
                  <input
                    name="name"
                    onChange={(event) => setName(event.target.value)}
                    required
                    value={name}
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
              </div>

              <label className="settings-field">
                <span>Description</span>
                <textarea
                  name="description"
                  onChange={(event) => setDescription(event.target.value)}
                  rows={6}
                  value={description}
                />
              </label>

              <label className="experiments-checkbox">
                <input
                  checked={isArchived}
                  onChange={(event) => setIsArchived(event.target.checked)}
                  type="checkbox"
                />
                <span>Archive this experiment instead of showing it in the default index.</span>
              </label>
            </fieldset>

            <div className="settings-action-row">
              <button className="settings-primary-action" type="submit">
                Save experiment
              </button>
              <button
                className="settings-danger-action"
                onClick={handleDelete}
                type="button"
              >
                Delete experiment
              </button>
            </div>
          </form>
        ) : (
          <div className="experiment-tab-panel" role="tabpanel">
            <span className="state-badge">{tabs.find((tab) => tab.value === activeTab)?.label}</span>
            <h3>{tabCopy[activeTab].heading}</h3>
            <p>{tabCopy[activeTab].description}</p>
          </div>
        )}
      </section>
    </div>
  );
}
