"use client";

import { startTransition, useState } from "react";

import { useAppShellState } from "@/components/providers/app-shell-provider";
import { EmptyState } from "@/components/states/empty-state";
import { useApiClient } from "@/lib/api/browser";
import {
  ApiClientError,
  type ExperimentResponse,
  type ListRunsRequest,
  type RunHistoryResponse,
} from "@/lib/api/client";

type RunsWorkspaceProps = {
  initialExperiments: ExperimentResponse[];
  initialRuns: RunHistoryResponse[];
};

type SortOption =
  | "costliest"
  | "fastest"
  | "latest"
  | "most_expensive"
  | "oldest"
  | "slowest";

type FilterState = {
  configId: string;
  createdFrom: string;
  createdTo: string;
  experimentId: string;
  model: string;
  provider: string;
  status: string;
  tag: string;
  sortOption: SortOption;
};

const DEFAULT_FILTERS: FilterState = {
  configId: "",
  createdFrom: "",
  createdTo: "",
  experimentId: "",
  model: "",
  provider: "",
  status: "",
  tag: "",
  sortOption: "latest",
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
    return "Not started";
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

function deriveOptions(values: string[]) {
  return [...new Set(values.filter((value) => value.trim().length > 0))].sort((left, right) =>
    left.localeCompare(right),
  );
}

function toDateBoundary(value: string, { endOfDay }: { endOfDay: boolean }) {
  if (!value) {
    return null;
  }

  return endOfDay ? `${value}T23:59:59Z` : `${value}T00:00:00Z`;
}

function toRunsRequest(filters: FilterState): ListRunsRequest {
  const sortMappings: Record<
    SortOption,
    NonNullable<Pick<ListRunsRequest, "sortBy" | "sortOrder">>
  > = {
    costliest: { sortBy: "estimated_cost_usd", sortOrder: "desc" },
    fastest: { sortBy: "latency_ms", sortOrder: "asc" },
    latest: { sortBy: "created_at", sortOrder: "desc" },
    most_expensive: { sortBy: "estimated_cost_usd", sortOrder: "asc" },
    oldest: { sortBy: "created_at", sortOrder: "asc" },
    slowest: { sortBy: "latency_ms", sortOrder: "desc" },
  };

  const sortSelection = sortMappings[filters.sortOption];

  return {
    experimentIds: filters.experimentId ? [filters.experimentId] : [],
    configIds: filters.configId ? [filters.configId] : [],
    providers: filters.provider ? [filters.provider] : [],
    models: filters.model ? [filters.model] : [],
    statuses: filters.status ? [filters.status] : [],
    tags: filters.tag ? [filters.tag] : [],
    createdFrom: toDateBoundary(filters.createdFrom, { endOfDay: false }),
    createdTo: toDateBoundary(filters.createdTo, { endOfDay: true }),
    sortBy: sortSelection.sortBy,
    sortOrder: sortSelection.sortOrder,
  };
}

export function RunsWorkspace({ initialExperiments, initialRuns }: RunsWorkspaceProps) {
  const apiClient = useApiClient();
  const { clearGlobalError, setGlobalError, startLoading, stopLoading } = useAppShellState();
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS);
  const [runs, setRuns] = useState(initialRuns);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const experiments = [...initialExperiments].sort((left, right) => left.name.localeCompare(right.name));
  const providers = deriveOptions(initialRuns.map((run) => run.provider));
  const models = deriveOptions(initialRuns.map((run) => run.model));
  const configs = [...initialRuns]
    .map((run) => ({
      id: run.config_id,
      label: `${run.config_name} ${run.config_version_label}`.trim(),
    }))
    .filter(
      (option, index, options) =>
        options.findIndex((candidate) => candidate.id === option.id) === index,
    )
    .sort((left, right) => left.label.localeCompare(right.label));
  const statuses = ["completed", "failed", "pending", "running"];

  const failedRunsCount = runs.filter((run) => run.status === "failed").length;
  const experimentCoverage = new Set(runs.map((run) => run.experiment_id)).size;
  const hasActiveFilters = Object.entries(filters).some(([key, value]) => {
    if (key === "sortOption") {
      return value !== DEFAULT_FILTERS.sortOption;
    }
    return value.length > 0;
  });

  async function refreshRuns(nextFilters: FilterState) {
    clearGlobalError();
    setIsRefreshing(true);
    startLoading();

    try {
      const nextRuns = await apiClient.runs.list(toRunsRequest(nextFilters));
      startTransition(() => {
        setRuns(nextRuns);
      });
    } catch (error) {
      const detail =
        error instanceof ApiClientError ? `${error.message} (${error.status})` : "Request failed.";
      setGlobalError({
        title: "Could not load run history",
        detail,
      });
    } finally {
      stopLoading();
      setIsRefreshing(false);
    }
  }

  function updateFilter<K extends keyof FilterState>(key: K, value: FilterState[K]) {
    setFilters((current) => ({
      ...current,
      [key]: value,
    }));
  }

  function handleApplyFilters() {
    void refreshRuns(filters);
  }

  function handleClearFilters() {
    startTransition(() => {
      setFilters(DEFAULT_FILTERS);
    });
    void refreshRuns(DEFAULT_FILTERS);
  }

  return (
    <div className="runs-shell" role="tabpanel">
      <section className="three-column-grid runs-summary-grid">
        <article className="shell-panel runs-summary-card">
          <p className="section-kicker">Visible runs</p>
          <h3>{runs.length}</h3>
          <p className="status-copy">Sort and filter history without leaving the shell.</p>
        </article>

        <article className="shell-panel runs-summary-card">
          <p className="section-kicker">Failed runs</p>
          <h3>{failedRunsCount}</h3>
          <p className="status-copy">Failed attempts stay in history to preserve the record.</p>
        </article>

        <article className="shell-panel runs-summary-card">
          <p className="section-kicker">Experiments covered</p>
          <h3>{experimentCoverage}</h3>
          <p className="status-copy">Every row remains scoped to the signed-in user.</p>
        </article>
      </section>

      <section className="shell-panel runs-card runs-card-accent">
        <div className="settings-card-header">
          <div>
            <p className="section-kicker">History filters</p>
            <h2>Slice run history by experiment, model, config, tag, and date.</h2>
          </div>
          <p className="experiments-list-meta">
            Server-side filters keep the page aligned with the API read model.
          </p>
        </div>

        <div className="settings-field-grid runs-filter-grid">
          <label className="settings-field">
            <span>Experiment</span>
            <select
              aria-label="Experiment"
              onChange={(event) => updateFilter("experimentId", event.target.value)}
              value={filters.experimentId}
            >
              <option value="">All experiments</option>
              {experiments.map((experiment) => (
                <option key={experiment.id} value={experiment.id}>
                  {experiment.name}
                </option>
              ))}
            </select>
          </label>

          <label className="settings-field">
            <span>Provider</span>
            <select
              aria-label="Provider"
              onChange={(event) => updateFilter("provider", event.target.value)}
              value={filters.provider}
            >
              <option value="">All providers</option>
              {providers.map((provider) => (
                <option key={provider} value={provider}>
                  {formatProvider(provider)}
                </option>
              ))}
            </select>
          </label>

          <label className="settings-field">
            <span>Model</span>
            <select
              aria-label="Model"
              onChange={(event) => updateFilter("model", event.target.value)}
              value={filters.model}
            >
              <option value="">All models</option>
              {models.map((model) => (
                <option key={model} value={model}>
                  {model}
                </option>
              ))}
            </select>
          </label>

          <label className="settings-field">
            <span>Config</span>
            <select
              aria-label="Config"
              onChange={(event) => updateFilter("configId", event.target.value)}
              value={filters.configId}
            >
              <option value="">All configs</option>
              {configs.map((config) => (
                <option key={config.id} value={config.id}>
                  {config.label}
                </option>
              ))}
            </select>
          </label>

          <label className="settings-field">
            <span>Status</span>
            <select
              aria-label="Status"
              onChange={(event) => updateFilter("status", event.target.value)}
              value={filters.status}
            >
              <option value="">All statuses</option>
              {statuses.map((status) => (
                <option key={status} value={status}>
                  {formatStatus(status)}
                </option>
              ))}
            </select>
          </label>

          <label className="settings-field">
            <span>Tag</span>
            <input
              aria-label="Tag"
              onChange={(event) => updateFilter("tag", event.target.value)}
              placeholder="priority"
              type="text"
              value={filters.tag}
            />
          </label>

          <label className="settings-field">
            <span>Date from</span>
            <input
              aria-label="Date from"
              onChange={(event) => updateFilter("createdFrom", event.target.value)}
              type="date"
              value={filters.createdFrom}
            />
          </label>

          <label className="settings-field">
            <span>Date to</span>
            <input
              aria-label="Date to"
              onChange={(event) => updateFilter("createdTo", event.target.value)}
              type="date"
              value={filters.createdTo}
            />
          </label>

          <label className="settings-field">
            <span>Sort by</span>
            <select
              aria-label="Sort by"
              onChange={(event) => updateFilter("sortOption", event.target.value as SortOption)}
              value={filters.sortOption}
            >
              <option value="latest">Latest first</option>
              <option value="oldest">Oldest first</option>
              <option value="fastest">Fastest first</option>
              <option value="slowest">Slowest first</option>
              <option value="costliest">Highest cost first</option>
              <option value="most_expensive">Lowest cost first</option>
            </select>
          </label>
        </div>

        <div className="settings-action-row">
          <button
            className="settings-primary-action"
            disabled={isRefreshing}
            onClick={handleApplyFilters}
            type="button"
          >
            Apply filters
          </button>
          <button
            className="settings-secondary-action"
            disabled={isRefreshing || !hasActiveFilters}
            onClick={handleClearFilters}
            type="button"
          >
            Clear filters
          </button>
        </div>
      </section>

      <section className="shell-panel runs-card">
        <div className="settings-card-header">
          <div>
            <p className="section-kicker">Run history</p>
            <h2>Readable status, provider, model, and experiment context in one table.</h2>
          </div>
          <p className="experiments-list-meta">
            The run detail page lands next, but this index already points to the exact record you
            need.
          </p>
        </div>

        {runs.length === 0 ? (
          <EmptyState
            description={
              hasActiveFilters
                ? "No owned runs matched the current filter set."
                : "Launch a config from an experiment to start building history."
            }
            label="Runs"
            title={hasActiveFilters ? "No runs match the current filters" : "No run history yet"}
          />
        ) : (
          <div className="runs-table-shell">
            <table className="runs-table">
              <thead>
                <tr>
                  <th scope="col">Started</th>
                  <th scope="col">Experiment</th>
                  <th scope="col">Config</th>
                  <th scope="col">Model</th>
                  <th scope="col">Status</th>
                  <th scope="col">Latency</th>
                  <th scope="col">Cost</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr key={run.id}>
                    <td>
                      <div className="runs-table-primary">{formatTimestamp(run.started_at)}</div>
                      <div className="runs-table-secondary">{run.test_case_input_preview}</div>
                    </td>
                    <td>
                      <div className="runs-table-primary">
                        {run.experiment_name ?? "Deleted experiment"}
                      </div>
                      <div className="runs-table-secondary">{run.workflow_mode}</div>
                    </td>
                    <td>
                      <div className="runs-table-primary">
                        {run.config_name} {run.config_version_label}
                      </div>
                      <div className="runs-table-secondary">
                        {run.tags.length > 0 ? run.tags.join(", ") : "No tags"}
                      </div>
                    </td>
                    <td>
                      <div className="runs-table-primary">{run.model}</div>
                      <div className="runs-table-secondary">{formatProvider(run.provider)}</div>
                    </td>
                    <td>
                      <span className={`run-status-pill run-status-pill-${run.status}`}>
                        {formatStatus(run.status)}
                      </span>
                    </td>
                    <td>{run.latency_ms === null ? "Unavailable" : `${run.latency_ms} ms`}</td>
                    <td>{formatCurrency(run.estimated_cost_usd)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
