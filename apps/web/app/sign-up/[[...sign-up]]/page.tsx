import { SignUp } from "@clerk/nextjs";
import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";

import { AuthScreen } from "@/components/auth/auth-screen";
import { publicAppConfig } from "@/lib/app-config";

export default async function SignUpPage() {
  const { userId } = await auth();

  if (userId) {
    redirect("/dashboard");
  }

  return (
    <AuthScreen
      alternateHref={publicAppConfig.clerkSignInUrl}
      alternateLabel="Already have an account? Sign in"
      description="Create a Clerk account to access your protected shell routes before later backlog items attach authenticated FastAPI requests."
      eyebrow="Sign up"
      title="Create a Benchloop session."
    >
      <SignUp />
    </AuthScreen>
  );
}
