"use client";

import { startTransition, useEffect, useState } from "react";

import { useAppShellState } from "@/components/providers/app-shell-provider";
import { useApiClient } from "@/lib/api/browser";
import {
  ApiClientError,
  type RunEvaluationResponse,
  type UpdateRunEvaluationRequest,
} from "@/lib/api/client";

import {
  EVALUATION_DIMENSIONS,
  formatDimensionScores,
  formatEvaluationNotes,
  formatEvaluationScore,
  formatEvaluationSignal,
} from "./run-evaluation-utils";

type FeedbackState =
  | {
      message: string;
      tone: "error" | "success";
    }
  | null;

type RunEvaluationEditorProps = {
  initialEvaluation: RunEvaluationResponse | null;
  onChange: (evaluation: RunEvaluationResponse | null) => void;
  runId: string;
};

type EvaluationFormState = {
  dimensionScores: Record<string, string>;
  notes: string;
  overallScore: string;
  thumbsSignal: "" | "down" | "up";
};

function toFormState(evaluation: RunEvaluationResponse | null): EvaluationFormState {
  return {
    dimensionScores: Object.fromEntries(
      EVALUATION_DIMENSIONS.map((dimension) => [
        dimension.key,
        evaluation?.dimension_scores[dimension.key]
          ? String(evaluation.dimension_scores[dimension.key])
          : "",
      ]),
    ),
    notes: evaluation?.notes ?? "",
    overallScore: evaluation?.overall_score ? String(evaluation.overall_score) : "",
    thumbsSignal: evaluation?.thumbs_signal ?? "",
  };
}

function buildPayload(state: EvaluationFormState): UpdateRunEvaluationRequest | null {
  const dimensionScores = Object.fromEntries(
    Object.entries(state.dimensionScores)
      .filter(([, value]) => value.length > 0)
      .map(([key, value]) => [key, Number(value)]),
  );
  const notes = state.notes.trim();
  const overallScore = state.overallScore ? Number(state.overallScore) : null;
  const thumbsSignal: "down" | "up" | null =
    state.thumbsSignal === "up" || state.thumbsSignal === "down" ? state.thumbsSignal : null;

  if (
    overallScore === null &&
    thumbsSignal === null &&
    notes.length === 0 &&
    Object.keys(dimensionScores).length === 0
  ) {
    return null;
  }

  return {
    overall_score: overallScore,
    dimension_scores: dimensionScores,
    thumbs_signal: thumbsSignal,
    notes: notes.length > 0 ? notes : null,
  };
}

function formatTimestamp(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function RunEvaluationEditor({
  initialEvaluation,
  onChange,
  runId,
}: RunEvaluationEditorProps) {
  const apiClient = useApiClient();
  const { clearGlobalError, setGlobalError, startLoading, stopLoading } = useAppShellState();
  const [currentEvaluation, setCurrentEvaluation] = useState(initialEvaluation);
  const [formState, setFormState] = useState<EvaluationFormState>(() => toFormState(initialEvaluation));
  const [feedback, setFeedback] = useState<FeedbackState>(null);
  const [activeAction, setActiveAction] = useState<"clear" | "save" | null>(null);

  useEffect(() => {
    setCurrentEvaluation(initialEvaluation);
    setFormState(toFormState(initialEvaluation));
  }, [initialEvaluation]);

  function updateField<K extends keyof EvaluationFormState>(key: K, value: EvaluationFormState[K]) {
    setFormState((current) => ({
      ...current,
      [key]: value,
    }));
  }

  function updateDimension(key: string, value: string) {
    setFormState((current) => ({
      ...current,
      dimensionScores: {
        ...current.dimensionScores,
        [key]: value,
      },
    }));
  }

  async function handleSave() {
    const payload = buildPayload(formState);
    if (!payload) {
      setFeedback({
        tone: "error",
        message: "Add a score, signal, notes, or dimension score before saving.",
      });
      return;
    }

    clearGlobalError();
    setFeedback(null);
    setActiveAction("save");
    startLoading();

    try {
      const evaluation = await apiClient.runs.updateEvaluation(runId, payload);
      startTransition(() => {
        setCurrentEvaluation(evaluation);
        setFormState(toFormState(evaluation));
        onChange(evaluation);
        setFeedback({
          tone: "success",
          message: "Saved manual evaluation.",
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
        title: "Could not save evaluation",
        detail,
      });
    } finally {
      stopLoading();
      setActiveAction(null);
    }
  }

  async function handleClearOrReset() {
    if (!currentEvaluation) {
      setFormState(toFormState(null));
      setFeedback(null);
      return;
    }

    clearGlobalError();
    setFeedback(null);
    setActiveAction("clear");
    startLoading();

    try {
      await apiClient.runs.deleteEvaluation(runId);
      startTransition(() => {
        setCurrentEvaluation(null);
        setFormState(toFormState(null));
        onChange(null);
        setFeedback({
          tone: "success",
          message: "Cleared manual evaluation.",
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
        title: "Could not clear evaluation",
        detail,
      });
    } finally {
      stopLoading();
      setActiveAction(null);
    }
  }

  return (
    <section className="shell-panel run-evaluation-card">
      {feedback ? (
        <div
          className={`settings-feedback settings-feedback-${feedback.tone}`}
          role={feedback.tone === "error" ? "alert" : "status"}
        >
          {feedback.message}
        </div>
      ) : null}

      <div className="settings-card-header">
        <div>
          <p className="section-kicker">Manual evaluation</p>
          <h3>Score, signal, and notes stay attached to this run record.</h3>
        </div>
        <p className="experiments-list-meta">
          Save from the current workflow instead of leaving compare or detail.
        </p>
      </div>

      <dl className="run-detail-meta-grid">
        <div>
          <dt>Current score</dt>
          <dd>{formatEvaluationScore(currentEvaluation)}</dd>
        </div>
        <div>
          <dt>Signal</dt>
          <dd>{formatEvaluationSignal(currentEvaluation)}</dd>
        </div>
        <div>
          <dt>Dimensions</dt>
          <dd>{formatDimensionScores(currentEvaluation)}</dd>
        </div>
        <div>
          <dt>Last updated</dt>
          <dd>{currentEvaluation ? formatTimestamp(currentEvaluation.updated_at) : "Not saved yet"}</dd>
        </div>
      </dl>

      <p className="run-helper-copy">{formatEvaluationNotes(currentEvaluation)}</p>

      <div className="settings-field-grid run-evaluation-grid">
        <label className="settings-field">
          <span>Overall score</span>
          <select
            aria-label="Overall score"
            onChange={(event) => updateField("overallScore", event.target.value)}
            value={formState.overallScore}
          >
            <option value="">Not scored</option>
            <option value="1">1/5</option>
            <option value="2">2/5</option>
            <option value="3">3/5</option>
            <option value="4">4/5</option>
            <option value="5">5/5</option>
          </select>
        </label>

        <label className="settings-field">
          <span>Thumbs signal</span>
          <select
            aria-label="Thumbs signal"
            onChange={(event) =>
              updateField("thumbsSignal", event.target.value as EvaluationFormState["thumbsSignal"])
            }
            value={formState.thumbsSignal}
          >
            <option value="">No signal</option>
            <option value="up">Thumbs up</option>
            <option value="down">Thumbs down</option>
          </select>
        </label>

        {EVALUATION_DIMENSIONS.map((dimension) => (
          <label className="settings-field" key={dimension.key}>
            <span>{dimension.label} score</span>
            <select
              aria-label={`${dimension.label} score`}
              onChange={(event) => updateDimension(dimension.key, event.target.value)}
              value={formState.dimensionScores[dimension.key] ?? ""}
            >
              <option value="">Not scored</option>
              <option value="1">1/5</option>
              <option value="2">2/5</option>
              <option value="3">3/5</option>
              <option value="4">4/5</option>
              <option value="5">5/5</option>
            </select>
          </label>
        ))}
      </div>

      <label className="settings-field">
        <span>Evaluation notes</span>
        <textarea
          aria-label="Evaluation notes"
          onChange={(event) => updateField("notes", event.target.value)}
          rows={4}
          value={formState.notes}
        />
      </label>

      <div className="settings-action-row">
        <button
          className="settings-primary-action"
          disabled={activeAction !== null}
          onClick={handleSave}
          type="button"
        >
          {activeAction === "save" ? "Saving evaluation..." : "Save evaluation"}
        </button>
        <button
          className="settings-secondary-action"
          disabled={activeAction !== null}
          onClick={handleClearOrReset}
          type="button"
        >
          {currentEvaluation ? "Clear evaluation" : "Reset form"}
        </button>
      </div>
    </section>
  );
}
