"use client";

import { startTransition, useState, type FormEvent } from "react";

import { useAppShellState } from "@/components/providers/app-shell-provider";
import { EmptyState } from "@/components/states/empty-state";
import { useApiClient } from "@/lib/api/browser";
import {
  ApiClientError,
  type CreateTestCaseRequest,
  type TestCaseResponse,
  type UpdateTestCaseRequest,
} from "@/lib/api/client";

type ExperimentTestCasesWorkspaceProps = {
  experimentId: string;
  initialTestCases: TestCaseResponse[];
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

function sortTestCases(testCases: TestCaseResponse[]) {
  return [...testCases].sort((left, right) => {
    const updatedComparison = right.updated_at.localeCompare(left.updated_at);
    if (updatedComparison !== 0) {
      return updatedComparison;
    }

    return left.id.localeCompare(right.id);
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
  if (compact.length <= 120) {
    return compact;
  }
  return `${compact.slice(0, 117)}...`;
}

export function ExperimentTestCasesWorkspace({
  experimentId,
  initialTestCases,
}: ExperimentTestCasesWorkspaceProps) {
  const apiClient = useApiClient();
  const { clearGlobalError, setGlobalError, startLoading, stopLoading } = useAppShellState();

  const [testCases, setTestCases] = useState(() => sortTestCases(initialTestCases));
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set());
  const [editingId, setEditingId] = useState<string | null>(null);
  const [activeAction, setActiveAction] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<FeedbackState>(null);

  const [inputText, setInputText] = useState("");
  const [expectedOutputText, setExpectedOutputText] = useState("");
  const [notes, setNotes] = useState("");
  const [tags, setTags] = useState("");

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
    setInputText("");
    setExpectedOutputText("");
    setNotes("");
    setTags("");
  }

  function buildPayload(): CreateTestCaseRequest | UpdateTestCaseRequest {
    return {
      input_text: inputText,
      expected_output_text: normalizeOptionalText(expectedOutputText),
      notes: normalizeOptionalText(notes),
      tags: parseTags(tags),
    };
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (editingId) {
      const payload = buildPayload();
      void runTask({
        actionKey: "save-test-case",
        errorTitle: "Could not save test case",
        successMessage: "Test case updated.",
        work: () => apiClient.experiments.updateTestCase(experimentId, editingId, payload),
        commit: (updatedTestCase) => {
          setTestCases((current) =>
            sortTestCases(
              current.map((testCase) => (testCase.id === updatedTestCase.id ? updatedTestCase : testCase)),
            ),
          );
          resetForm();
        },
      });
      return;
    }

    const payload = buildPayload();
    void runTask({
      actionKey: "create-test-case",
      errorTitle: "Could not create test case",
      successMessage: "Test case created.",
      work: () => apiClient.experiments.createTestCase(experimentId, payload),
      commit: (createdTestCase) => {
        setTestCases((current) => sortTestCases([createdTestCase, ...current]));
        setSelectedIds((current) => new Set(current).add(createdTestCase.id));
        resetForm();
      },
    });
  }

  function handleEdit(testCase: TestCaseResponse) {
    setEditingId(testCase.id);
    setInputText(testCase.input_text);
    setExpectedOutputText(testCase.expected_output_text ?? "");
    setNotes(testCase.notes ?? "");
    setTags(serializeTags(testCase.tags));
    setFeedback(null);
  }

  function handleDuplicate(testCaseId: string) {
    void runTask({
      actionKey: `duplicate-${testCaseId}`,
      errorTitle: "Could not duplicate test case",
      successMessage: "Test case duplicated.",
      work: () => apiClient.experiments.duplicateTestCase(experimentId, testCaseId),
      commit: (duplicatedTestCase) => {
        setTestCases((current) => sortTestCases([duplicatedTestCase, ...current]));
        setSelectedIds((current) => new Set(current).add(duplicatedTestCase.id));
      },
    });
  }

  function handleDelete(testCaseId: string) {
    void runTask({
      actionKey: `delete-${testCaseId}`,
      errorTitle: "Could not delete test case",
      successMessage: "Test case deleted.",
      work: async () => {
        await apiClient.experiments.deleteTestCase(experimentId, testCaseId);
      },
      commit: () => {
        setTestCases((current) => current.filter((testCase) => testCase.id !== testCaseId));
        setSelectedIds((current) => {
          const nextSelectedIds = new Set(current);
          nextSelectedIds.delete(testCaseId);
          return nextSelectedIds;
        });
        if (editingId === testCaseId) {
          resetForm();
        }
      },
    });
  }

  function toggleSelection(testCaseId: string) {
    setSelectedIds((current) => {
      const nextSelectedIds = new Set(current);
      if (nextSelectedIds.has(testCaseId)) {
        nextSelectedIds.delete(testCaseId);
      } else {
        nextSelectedIds.add(testCaseId);
      }
      return nextSelectedIds;
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
              <p className="section-kicker">Test case editor</p>
              <h3>{isEditing ? "Revise the selected input." : "Add a reusable input."}</h3>
            </div>
            <p className="experiments-list-meta">
              {isEditing ? "Editing existing test case" : "Create a new case for later run launch"}
            </p>
          </div>

          <form className="settings-form" onSubmit={handleSubmit}>
            <fieldset className="settings-fieldset" disabled={activeAction !== null}>
              <label className="settings-field">
                <span>Input text</span>
                <textarea
                  name="input_text"
                  onChange={(event) => setInputText(event.target.value)}
                  required
                  rows={6}
                  value={inputText}
                />
              </label>

              <label className="settings-field">
                <span>Expected output</span>
                <textarea
                  name="expected_output_text"
                  onChange={(event) => setExpectedOutputText(event.target.value)}
                  rows={4}
                  value={expectedOutputText}
                />
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

              <label className="settings-field">
                <span>Test case tags</span>
                <input
                  name="tags"
                  onChange={(event) => setTags(event.target.value)}
                  placeholder="billing, escalation"
                  value={tags}
                />
              </label>
            </fieldset>

            <div className="settings-action-row">
              <button className="settings-primary-action" type="submit">
                {isEditing ? "Save test case" : "Create test case"}
              </button>
              {isEditing ? (
                <button
                  className="settings-secondary-action"
                  onClick={resetForm}
                  type="button"
                >
                  Cancel edit
                </button>
              ) : null}
            </div>
          </form>
        </article>

        <article className="shell-panel experiments-card">
          <div className="experiments-list-header">
            <div>
              <p className="section-kicker">Selection-ready list</p>
              <h3>Keep reusable cases close to the experiment.</h3>
            </div>
            <p className="experiments-list-meta">{selectedIds.size} selected</p>
          </div>

          {testCases.length === 0 ? (
            <EmptyState
              description="Create the first test case so this experiment has a stable input ready for later run launch."
              label="Test cases"
              title="No test cases yet"
            />
          ) : (
            <div className="experiments-card-grid">
              {testCases.map((testCase) => {
                const isSelected = selectedIds.has(testCase.id);

                return (
                  <article className="experiment-card test-case-card" key={testCase.id}>
                    <div className="experiment-card-header">
                      <label className="experiments-checkbox test-case-select">
                        <input
                          aria-label="Select test case"
                          checked={isSelected}
                          onChange={() => toggleSelection(testCase.id)}
                          type="checkbox"
                        />
                        <span>{buildPreview(testCase.input_text)}</span>
                      </label>
                      <span className="state-badge">{isSelected ? "Selected" : "Available"}</span>
                    </div>

                    <dl className="experiment-metadata">
                      <div>
                        <dt>Expected output</dt>
                        <dd>{testCase.expected_output_text ?? "No expected output recorded."}</dd>
                      </div>
                      <div>
                        <dt>Notes</dt>
                        <dd>{testCase.notes ?? "No notes recorded."}</dd>
                      </div>
                      <div>
                        <dt>Tags</dt>
                        <dd>{testCase.tags.length > 0 ? serializeTags(testCase.tags) : "No tags yet."}</dd>
                      </div>
                      <div>
                        <dt>Last updated</dt>
                        <dd>{formatTimestamp(testCase.updated_at)}</dd>
                      </div>
                    </dl>

                    <div className="settings-action-row">
                      <button
                        className="settings-secondary-action"
                        onClick={() => handleEdit(testCase)}
                        type="button"
                      >
                        Edit test case
                      </button>
                      <button
                        className="settings-secondary-action"
                        onClick={() => handleDuplicate(testCase.id)}
                        type="button"
                      >
                        Duplicate test case
                      </button>
                      <button
                        className="settings-danger-action"
                        onClick={() => handleDelete(testCase.id)}
                        type="button"
                      >
                        Delete test case
                      </button>
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </article>
      </section>
    </div>
  );
}
