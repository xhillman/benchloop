import type { RunEvaluationResponse } from "@/lib/api/client";

export const EVALUATION_DIMENSIONS = [
  { key: "accuracy", label: "Accuracy" },
  { key: "clarity", label: "Clarity" },
  { key: "completeness", label: "Completeness" },
] as const;

export function formatEvaluationScore(evaluation: RunEvaluationResponse | null) {
  return evaluation?.overall_score ? `${evaluation.overall_score}/5` : "Not scored";
}

export function formatEvaluationSignal(evaluation: RunEvaluationResponse | null) {
  if (evaluation?.thumbs_signal === "up") {
    return "Thumbs up";
  }
  if (evaluation?.thumbs_signal === "down") {
    return "Thumbs down";
  }
  return "No signal";
}

export function formatEvaluationNotes(evaluation: RunEvaluationResponse | null) {
  return evaluation?.notes?.trim() ? evaluation.notes : "No notes recorded.";
}

export function formatDimensionScores(evaluation: RunEvaluationResponse | null) {
  if (!evaluation) {
    return "No dimension scores";
  }

  const scoredDimensions = EVALUATION_DIMENSIONS.filter(
    (dimension) => evaluation.dimension_scores[dimension.key],
  ).map(
    (dimension) => `${dimension.label} ${evaluation.dimension_scores[dimension.key]}/5`,
  );

  return scoredDimensions.length > 0 ? scoredDimensions.join(", ") : "No dimension scores";
}
