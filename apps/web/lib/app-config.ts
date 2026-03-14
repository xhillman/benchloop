const DEFAULT_APP_URL = "http://localhost:3000";
const DEFAULT_API_BASE_URL = "http://localhost:8000";

export const publicAppConfig = {
  appUrl: process.env.NEXT_PUBLIC_APP_URL ?? DEFAULT_APP_URL,
  apiBaseUrl: process.env.NEXT_PUBLIC_API_BASE_URL ?? DEFAULT_API_BASE_URL,
};
