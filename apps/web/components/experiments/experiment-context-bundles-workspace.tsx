"use client";

import { startTransition, useState, type FormEvent } from "react";

import { useAppShellState } from "@/components/providers/app-shell-provider";
import { EmptyState } from "@/components/states/empty-state";
import { useApiClient } from "@/lib/api/browser";
import {
  ApiClientError,
  type ContextBundleResponse,
  type CreateContextBundleRequest,
  type UpdateContextBundleRequest,
} from "@/lib/api/client";

type ExperimentContextBundlesWorkspaceProps = {
  contextBundles: ContextBundleResponse[];
  experimentId: string;
  onContextBundleDeleted?: (contextBundleId: string) => void;
  onContextBundlesChange?: (contextBundles: ContextBundleResponse[]) => void;
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

function sortContextBundles(contextBundles: ContextBundleResponse[]) {
  return [...contextBundles].sort((left, right) => {
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

function buildPreview(value: string) {
  const compact = value.replace(/\s+/g, " ").trim();
  if (compact.length <= 140) {
    return compact;
  }
  return `${compact.slice(0, 137)}...`;
}

export function ExperimentContextBundlesWorkspace({
  contextBundles,
  experimentId,
  onContextBundleDeleted,
  onContextBundlesChange,
}: ExperimentContextBundlesWorkspaceProps) {
  const apiClient = useApiClient();
  const { clearGlobalError, setGlobalError, startLoading, stopLoading } = useAppShellState();

  const [editingId, setEditingId] = useState<string | null>(null);
  const [activeAction, setActiveAction] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<FeedbackState>(null);

  const [name, setName] = useState("");
  const [contentText, setContentText] = useState("");
  const [notes, setNotes] = useState("");

  const sortedContextBundles = sortContextBundles(contextBundles);

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

  function resetForm() {
    setEditingId(null);
    setName("");
    setContentText("");
    setNotes("");
  }

  function buildPayload(): CreateContextBundleRequest | UpdateContextBundleRequest {
    return {
      name,
      content_text: contentText,
      notes: normalizeOptionalText(notes),
    };
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (editingId) {
      const payload = buildPayload();
      void runTask({
        actionKey: "save-context-bundle",
        errorTitle: "Could not save context bundle",
        successMessage: "Context bundle updated.",
        work: () => apiClient.experiments.updateContextBundle(experimentId, editingId, payload),
        commit: (updatedContextBundle) => {
          const nextContextBundles = sortContextBundles(
            contextBundles.map((contextBundle) =>
              contextBundle.id === updatedContextBundle.id ? updatedContextBundle : contextBundle,
            ),
          );
          onContextBundlesChange?.(nextContextBundles);
          resetForm();
        },
      });
      return;
    }

    const payload = buildPayload();
    void runTask({
      actionKey: "create-context-bundle",
      errorTitle: "Could not create context bundle",
      successMessage: "Context bundle created.",
      work: () => apiClient.experiments.createContextBundle(experimentId, payload),
      commit: (createdContextBundle) => {
        const nextContextBundles = sortContextBundles([createdContextBundle, ...contextBundles]);
        onContextBundlesChange?.(nextContextBundles);
        resetForm();
      },
    });
  }

  function handleEdit(contextBundle: ContextBundleResponse) {
    setEditingId(contextBundle.id);
    setName(contextBundle.name);
    setContentText(contextBundle.content_text);
    setNotes(contextBundle.notes ?? "");
    setFeedback(null);
  }

  function handleDelete(contextBundleId: string) {
    void runTask({
      actionKey: `delete-${contextBundleId}`,
      errorTitle: "Could not delete context bundle",
      successMessage: "Context bundle deleted.",
      work: async () => {
        await apiClient.experiments.deleteContextBundle(experimentId, contextBundleId);
      },
      commit: () => {
        onContextBundlesChange?.(
          sortContextBundles(
            contextBundles.filter((contextBundle) => contextBundle.id !== contextBundleId),
          ),
        );
        onContextBundleDeleted?.(contextBundleId);
        if (editingId === contextBundleId) {
          resetForm();
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

      <section className="two-column-grid experiments-controls-grid">
        <article className="shell-panel experiments-card experiments-card-accent">
          <div className="settings-card-header">
            <div>
              <p className="section-kicker">Context bundle editor</p>
              <h3>{isEditing ? "Revise the selected bundle." : "Store reusable grounding context."}</h3>
            </div>
            <p className="experiments-list-meta">
              Keep policy text, product facts, or domain notes reusable per experiment.
            </p>
          </div>

          <form className="settings-form" onSubmit={handleSubmit}>
            <fieldset className="settings-fieldset" disabled={activeAction !== null}>
              <label className="settings-field">
                <span>Name</span>
                <input name="name" onChange={(event) => setName(event.target.value)} required value={name} />
              </label>

              <label className="settings-field">
                <span>Context content</span>
                <textarea
                  name="content_text"
                  onChange={(event) => setContentText(event.target.value)}
                  required
                  rows={8}
                  value={contentText}
                />
                <small className="run-helper-copy">
                  Save the exact text you want later prompt-plus-context runs to snapshot.
                </small>
              </label>

              <label className="settings-field">
                <span>Notes</span>
                <textarea
                  name="notes"
                  onChange={(event) => setNotes(event.target.value)}
                  rows={3}
                  value={notes}
                />
              </label>
            </fieldset>

            <div className="settings-action-row">
              <button className="settings-primary-action" type="submit">
                {isEditing ? "Save context bundle" : "Create context bundle"}
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
              <p className="section-kicker">Saved bundles</p>
              <h3>Reuse the same context across multiple configs.</h3>
            </div>
            <p className="experiments-list-meta">{contextBundles.length} saved</p>
          </div>

          {sortedContextBundles.length === 0 ? (
            <EmptyState
              description="Save the first reusable block of grounding text so configs can attach it later."
              label="Context bundles"
              title="No context bundles yet"
            />
          ) : (
            <div className="experiments-card-grid">
              {sortedContextBundles.map((contextBundle) => (
                <article className="experiment-card test-case-card" key={contextBundle.id}>
                  <div className="experiment-card-header">
                    <div>
                      <p className="section-kicker">Reusable context</p>
                      <h3>{contextBundle.name}</h3>
                    </div>
                    <span className="state-badge">Saved</span>
                  </div>

                  <dl className="experiment-metadata">
                    <div>
                      <dt>Preview</dt>
                      <dd>{buildPreview(contextBundle.content_text)}</dd>
                    </div>
                    <div>
                      <dt>Notes</dt>
                      <dd>{contextBundle.notes ?? "No notes recorded."}</dd>
                    </div>
                    <div>
                      <dt>Last updated</dt>
                      <dd>{formatTimestamp(contextBundle.updated_at)}</dd>
                    </div>
                  </dl>

                  <div className="settings-action-row">
                    <button
                      className="settings-secondary-action"
                      onClick={() => handleEdit(contextBundle)}
                      type="button"
                    >
                      Edit context bundle
                    </button>
                    <button
                      className="settings-danger-action"
                      onClick={() => handleDelete(contextBundle.id)}
                      type="button"
                    >
                      Delete context bundle
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
