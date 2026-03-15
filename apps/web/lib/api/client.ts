import { publicAppConfig } from "@/lib/app-config";

type JsonPrimitive = boolean | null | number | string;
type JsonValue = JsonPrimitive | JsonValue[] | { [key: string]: JsonValue };

type TokenProvider = () => Promise<string | null> | string | null;

type ErrorEnvelope = {
  error?: {
    code?: string;
    details?: unknown;
    message?: string;
  };
};

export type HealthStatusResponse = {
  environment: string;
  service: string;
  status: string;
};

export type AuthMeResponse = {
  external_user_id: string;
};

export type UserSettingsResponse = {
  default_provider: string | null;
  default_model: string | null;
  timezone: string | null;
};

export type UpdateUserSettingsRequest = {
  default_provider: string | null;
  default_model: string | null;
  timezone: string | null;
};

export type UserProviderCredentialResponse = {
  id: string;
  provider: string;
  key_label: string | null;
  masked_api_key: string;
  validation_status: string;
  last_validated_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ExperimentResponse = {
  id: string;
  name: string;
  description: string | null;
  tags: string[];
  is_archived: boolean;
  created_at: string;
  updated_at: string;
};

export type TestCaseResponse = {
  id: string;
  experiment_id: string;
  input_text: string;
  expected_output_text: string | null;
  notes: string | null;
  tags: string[];
  created_at: string;
  updated_at: string;
};

export type ConfigResponse = {
  id: string;
  experiment_id: string;
  name: string;
  version_label: string;
  description: string | null;
  provider: string;
  model: string;
  workflow_mode: string;
  system_prompt: string | null;
  user_prompt_template: string;
  temperature: number;
  max_output_tokens: number;
  top_p: number | null;
  context_bundle_id: string | null;
  tags: string[];
  is_baseline: boolean;
  created_at: string;
  updated_at: string;
};

export type RunConfigSnapshot = {
  config_id: string;
  name: string;
  version_label: string;
  description: string | null;
  provider: string;
  model: string;
  workflow_mode: string;
  system_prompt_template: string | null;
  rendered_system_prompt: string | null;
  user_prompt_template: string;
  rendered_user_prompt: string;
  temperature: number;
  max_output_tokens: number;
  top_p: number | null;
  context_bundle_id: string | null;
  tags: string[];
  is_baseline: boolean;
};

export type RunInputSnapshot = {
  test_case_id: string;
  input_text: string;
  expected_output_text: string | null;
  notes: string | null;
  tags: string[];
};

export type RunContextSnapshot = {
  source: "bundle" | "inline";
  bundle_id: string | null;
  name: string | null;
  content_text: string;
  notes: string | null;
};

export type RunResponse = {
  id: string;
  experiment_id: string;
  test_case_id: string;
  config_id: string;
  credential_id: string | null;
  status: string;
  provider: string;
  model: string;
  workflow_mode: string;
  config_snapshot: RunConfigSnapshot;
  input_snapshot: RunInputSnapshot;
  context_snapshot: RunContextSnapshot | null;
  output_text: string | null;
  error_message: string | null;
  usage_input_tokens: number | null;
  usage_output_tokens: number | null;
  usage_total_tokens: number | null;
  latency_ms: number | null;
  estimated_cost_usd: number | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
};

export type RunHistoryResponse = {
  id: string;
  experiment_id: string;
  experiment_name: string | null;
  test_case_id: string;
  config_id: string;
  config_name: string;
  config_version_label: string;
  test_case_input_preview: string;
  status: string;
  provider: string;
  model: string;
  workflow_mode: string;
  tags: string[];
  latency_ms: number | null;
  estimated_cost_usd: number | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};

export type ListExperimentsRequest = {
  search?: string | null;
  tags?: string[];
  includeArchived?: boolean;
};

export type CreateExperimentRequest = {
  name: string;
  description: string | null;
  tags: string[];
};

export type UpdateExperimentRequest = CreateExperimentRequest & {
  is_archived: boolean;
};

export type CreateTestCaseRequest = {
  input_text: string;
  expected_output_text: string | null;
  notes: string | null;
  tags: string[];
};

export type UpdateTestCaseRequest = CreateTestCaseRequest;

export type CreateConfigRequest = {
  name: string;
  version_label: string;
  description: string | null;
  provider: string;
  model: string;
  workflow_mode: string;
  system_prompt: string | null;
  user_prompt_template: string;
  temperature: number;
  max_output_tokens: number;
  top_p: number | null;
  context_bundle_id: string | null;
  tags: string[];
  is_baseline: boolean;
};

export type UpdateConfigRequest = CreateConfigRequest;

export type LaunchRunRequest = {
  test_case_id: string;
  config_id: string;
};

export type LaunchBatchRunsRequest = {
  test_case_id: string;
  config_ids: string[];
};

export type ListRunsRequest = {
  experimentIds?: string[];
  configIds?: string[];
  providers?: string[];
  models?: string[];
  statuses?: string[];
  tags?: string[];
  createdFrom?: string | null;
  createdTo?: string | null;
  sortBy?: "created_at" | "estimated_cost_usd" | "finished_at" | "latency_ms";
  sortOrder?: "asc" | "desc";
};

export type CreateUserProviderCredentialRequest = {
  provider: string;
  api_key: string;
  key_label: string | null;
};

export type ReplaceUserProviderCredentialRequest = {
  api_key: string;
  key_label: string | null;
};

export type ApiRequestOptions = Omit<RequestInit, "body" | "headers" | "method"> & {
  auth?: boolean;
  body?: BodyInit | JsonValue | null;
  headers?: HeadersInit;
  method?: "DELETE" | "GET" | "PATCH" | "POST" | "PUT";
};

export type ApiClientOptions = {
  baseUrl?: string;
  fetch?: typeof fetch;
  getToken?: TokenProvider;
};

type ApiClientErrorOptions = {
  code: string;
  details: unknown;
  message: string;
  path: string;
  status: number;
};

export class ApiClientError extends Error {
  readonly code: string;
  readonly details: unknown;
  readonly path: string;
  readonly status: number;

  constructor({ code, details, message, path, status }: ApiClientErrorOptions) {
    super(message);
    this.name = "ApiClientError";
    this.code = code;
    this.details = details;
    this.path = path;
    this.status = status;
  }
}

type RequestFunction = <TResponse>(path: string, options?: ApiRequestOptions) => Promise<TResponse>;

function isPlainJsonBody(value: ApiRequestOptions["body"]): value is JsonValue {
  if (value === null || value === undefined) {
    return false;
  }

  if (typeof value === "string") {
    return false;
  }

  if (value instanceof ArrayBuffer || value instanceof Blob || value instanceof FormData) {
    return false;
  }

  if (value instanceof URLSearchParams) {
    return false;
  }

  if (ArrayBuffer.isView(value)) {
    return false;
  }

  return true;
}

function buildUrl(baseUrl: string, path: string) {
  return new URL(path, baseUrl).toString();
}

function buildExperimentsPath({
  includeArchived = false,
  search,
  tags = [],
}: ListExperimentsRequest = {}) {
  const searchParams = new URLSearchParams();

  if (search && search.trim().length > 0) {
    searchParams.set("search", search.trim());
  }

  for (const tag of tags) {
    const normalizedTag = tag.trim().toLowerCase();
    if (normalizedTag.length > 0) {
      searchParams.append("tag", normalizedTag);
    }
  }

  if (includeArchived) {
    searchParams.set("include_archived", "true");
  }

  const query = searchParams.toString();
  return query.length > 0 ? `/api/v1/experiments?${query}` : "/api/v1/experiments";
}

function buildRunsPath({
  experimentIds = [],
  configIds = [],
  providers = [],
  models = [],
  statuses = [],
  tags = [],
  createdFrom,
  createdTo,
  sortBy,
  sortOrder,
}: ListRunsRequest = {}) {
  const searchParams = new URLSearchParams();

  for (const experimentId of experimentIds) {
    if (experimentId.trim().length > 0) {
      searchParams.append("experiment_id", experimentId);
    }
  }

  for (const configId of configIds) {
    if (configId.trim().length > 0) {
      searchParams.append("config_id", configId);
    }
  }

  for (const provider of providers) {
    const normalizedProvider = provider.trim().toLowerCase();
    if (normalizedProvider.length > 0) {
      searchParams.append("provider", normalizedProvider);
    }
  }

  for (const model of models) {
    const normalizedModel = model.trim().toLowerCase();
    if (normalizedModel.length > 0) {
      searchParams.append("model", normalizedModel);
    }
  }

  for (const status of statuses) {
    const normalizedStatus = status.trim().toLowerCase();
    if (normalizedStatus.length > 0) {
      searchParams.append("status", normalizedStatus);
    }
  }

  for (const tag of tags) {
    const normalizedTag = tag.trim().toLowerCase();
    if (normalizedTag.length > 0) {
      searchParams.append("tag", normalizedTag);
    }
  }

  if (createdFrom && createdFrom.trim().length > 0) {
    searchParams.set("created_from", createdFrom);
  }

  if (createdTo && createdTo.trim().length > 0) {
    searchParams.set("created_to", createdTo);
  }

  if (sortBy) {
    searchParams.set("sort_by", sortBy);
  }

  if (sortOrder) {
    searchParams.set("sort_order", sortOrder);
  }

  const query = searchParams.toString();
  return query.length > 0 ? `/api/v1/runs?${query}` : "/api/v1/runs";
}

async function readResponseBody(response: Response): Promise<unknown> {
  if (response.status === 204) {
    return undefined;
  }

  const contentType = response.headers.get("content-type") ?? "";

  if (!contentType.includes("application/json")) {
    return undefined;
  }

  try {
    return await response.json();
  } catch {
    return undefined;
  }
}

function toApiClientError(response: Response, payload: unknown, path: string) {
  const envelope = payload as ErrorEnvelope | undefined;
  const code = envelope?.error?.code ?? "http_error";
  const message = envelope?.error?.message ?? response.statusText ?? "Request failed.";
  const details = envelope?.error?.details ?? null;

  return new ApiClientError({
    code,
    details,
    message,
    path,
    status: response.status,
  });
}

export function createApiClient({
  baseUrl = publicAppConfig.apiBaseUrl,
  fetch: fetchImplementation = fetch,
  getToken,
}: ApiClientOptions = {}) {
  const request: RequestFunction = async <TResponse>(
    path: string,
    {
      auth = true,
      body,
      headers: headerInit,
      method = "GET",
      ...requestInit
    }: ApiRequestOptions = {},
  ) => {
    const headers = new Headers(headerInit);

    if (auth && getToken) {
      const token = await getToken();

      if (token) {
        headers.set("Authorization", `Bearer ${token}`);
      }
    }

    let requestBody: BodyInit | null | undefined;

    if (isPlainJsonBody(body)) {
      if (!headers.has("Content-Type")) {
        headers.set("Content-Type", "application/json");
      }

      requestBody = JSON.stringify(body);
    } else {
      requestBody = body;
    }

    const response = await fetchImplementation(buildUrl(baseUrl, path), {
      ...requestInit,
      body: requestBody,
      headers,
      method,
    });
    const payload = await readResponseBody(response);

    if (!response.ok) {
      throw toApiClientError(response, payload, path);
    }

    return payload as TResponse;
  };

  return {
    auth: {
      getMe: () => request<AuthMeResponse>("/api/v1/auth/me"),
    },
    health: {
      getStatus: () =>
        request<HealthStatusResponse>("/api/v1/health", {
          auth: false,
        }),
    },
    experiments: {
      cloneConfig: (experimentId: string, configId: string) =>
        request<ConfigResponse>(`/api/v1/experiments/${experimentId}/configs/${configId}/clone`, {
          method: "POST",
        }),
      launchBatchRuns: (experimentId: string, payload: LaunchBatchRunsRequest) =>
        request<RunResponse[]>(`/api/v1/experiments/${experimentId}/runs/batch`, {
          body: payload,
          method: "POST",
        }),
      launchRun: (experimentId: string, payload: LaunchRunRequest) =>
        request<RunResponse>(`/api/v1/experiments/${experimentId}/runs`, {
          body: payload,
          method: "POST",
        }),
      createConfig: (experimentId: string, payload: CreateConfigRequest) =>
        request<ConfigResponse>(`/api/v1/experiments/${experimentId}/configs`, {
          body: payload,
          method: "POST",
        }),
      create: (payload: CreateExperimentRequest) =>
        request<ExperimentResponse>("/api/v1/experiments", {
          body: payload,
          method: "POST",
        }),
      delete: (experimentId: string) =>
        request<void>(`/api/v1/experiments/${experimentId}`, {
          method: "DELETE",
        }),
      deleteConfig: (experimentId: string, configId: string) =>
        request<void>(`/api/v1/experiments/${experimentId}/configs/${configId}`, {
          method: "DELETE",
        }),
      deleteTestCase: (experimentId: string, testCaseId: string) =>
        request<void>(`/api/v1/experiments/${experimentId}/test-cases/${testCaseId}`, {
          method: "DELETE",
        }),
      duplicateTestCase: (experimentId: string, testCaseId: string) =>
        request<TestCaseResponse>(
          `/api/v1/experiments/${experimentId}/test-cases/${testCaseId}/duplicate`,
          {
            method: "POST",
          },
        ),
      get: (experimentId: string) =>
        request<ExperimentResponse>(`/api/v1/experiments/${experimentId}`),
      listConfigs: (experimentId: string) =>
        request<ConfigResponse[]>(`/api/v1/experiments/${experimentId}/configs`),
      listTestCases: (experimentId: string) =>
        request<TestCaseResponse[]>(`/api/v1/experiments/${experimentId}/test-cases`),
      list: (params?: ListExperimentsRequest) =>
        request<ExperimentResponse[]>(buildExperimentsPath(params)),
      markConfigBaseline: (experimentId: string, configId: string) =>
        request<ConfigResponse>(
          `/api/v1/experiments/${experimentId}/configs/${configId}/baseline`,
          {
            method: "POST",
          },
        ),
      createTestCase: (experimentId: string, payload: CreateTestCaseRequest) =>
        request<TestCaseResponse>(`/api/v1/experiments/${experimentId}/test-cases`, {
          body: payload,
          method: "POST",
        }),
      updateConfig: (experimentId: string, configId: string, payload: UpdateConfigRequest) =>
        request<ConfigResponse>(`/api/v1/experiments/${experimentId}/configs/${configId}`, {
          body: payload,
          method: "PUT",
        }),
      updateTestCase: (
        experimentId: string,
        testCaseId: string,
        payload: UpdateTestCaseRequest,
      ) =>
        request<TestCaseResponse>(`/api/v1/experiments/${experimentId}/test-cases/${testCaseId}`, {
          body: payload,
          method: "PUT",
        }),
      update: (experimentId: string, payload: UpdateExperimentRequest) =>
        request<ExperimentResponse>(`/api/v1/experiments/${experimentId}`, {
          body: payload,
          method: "PUT",
        }),
    },
    runs: {
      list: (params?: ListRunsRequest) => request<RunHistoryResponse[]>(buildRunsPath(params)),
    },
    settings: {
      createCredential: (payload: CreateUserProviderCredentialRequest) =>
        request<UserProviderCredentialResponse>("/api/v1/settings/credentials", {
          body: payload,
          method: "POST",
        }),
      deleteCredential: (credentialId: string) =>
        request<void>(`/api/v1/settings/credentials/${credentialId}`, {
          method: "DELETE",
        }),
      get: () => request<UserSettingsResponse>("/api/v1/settings"),
      listCredentials: () =>
        request<UserProviderCredentialResponse[]>("/api/v1/settings/credentials"),
      replaceCredential: (credentialId: string, payload: ReplaceUserProviderCredentialRequest) =>
        request<UserProviderCredentialResponse>(`/api/v1/settings/credentials/${credentialId}`, {
          body: payload,
          method: "PUT",
        }),
      update: (payload: UpdateUserSettingsRequest) =>
        request<UserSettingsResponse>("/api/v1/settings", {
          body: payload,
          method: "PUT",
        }),
      validateCredential: (credentialId: string) =>
        request<UserProviderCredentialResponse>(
          `/api/v1/settings/credentials/${credentialId}/validate`,
          {
            method: "POST",
          },
        ),
    },
    request,
  };
}

export type BenchloopApiClient = ReturnType<typeof createApiClient>;
