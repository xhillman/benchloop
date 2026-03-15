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
