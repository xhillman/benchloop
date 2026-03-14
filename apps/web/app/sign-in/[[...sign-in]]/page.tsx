import { SignIn } from "@clerk/nextjs";
import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";

import { AuthScreen } from "@/components/auth/auth-screen";
import { publicAppConfig } from "@/lib/app-config";

export default async function SignInPage() {
  const { userId } = await auth();

  if (userId) {
    redirect("/dashboard");
  }

  return (
    <AuthScreen
      alternateHref={publicAppConfig.clerkSignUpUrl}
      alternateLabel="Need an account? Sign up"
      description="Sign in to reach the protected product shell. Product behavior still lives behind the FastAPI API surface."
      eyebrow="Sign in"
      title="Enter the Benchloop workbench."
    >
      <SignIn />
    </AuthScreen>
  );
}
