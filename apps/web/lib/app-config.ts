const DEFAULT_APP_URL = "http://localhost:3000";
const DEFAULT_API_BASE_URL = "http://localhost:8000";
const DEFAULT_SIGN_IN_URL = "/sign-in";
const DEFAULT_SIGN_UP_URL = "/sign-up";

export const publicAppConfig = {
  appUrl: process.env.NEXT_PUBLIC_APP_URL ?? DEFAULT_APP_URL,
  apiBaseUrl: process.env.NEXT_PUBLIC_API_BASE_URL ?? DEFAULT_API_BASE_URL,
  clerkSignInUrl: process.env.NEXT_PUBLIC_CLERK_SIGN_IN_URL ?? DEFAULT_SIGN_IN_URL,
  clerkSignUpUrl: process.env.NEXT_PUBLIC_CLERK_SIGN_UP_URL ?? DEFAULT_SIGN_UP_URL,
};
