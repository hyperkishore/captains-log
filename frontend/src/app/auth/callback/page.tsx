"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getSupabase } from "@/lib/supabase";

export default function AuthCallbackPage() {
  const router = useRouter();

  useEffect(() => {
    const supabase = getSupabase();
    if (!supabase) {
      router.push("/login?error=auth_misconfigured");
      return;
    }

    // Supabase handles the code exchange automatically via the URL hash
    // Just wait for the session to be established, then redirect
    const handleCallback = async () => {
      const { error } = await supabase.auth.getSession();
      if (error) {
        router.push("/login?error=callback_failed");
      } else {
        router.push("/");
      }
    };

    handleCallback();
  }, [router]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-zinc-950">
      <div className="text-zinc-400">Signing in...</div>
    </div>
  );
}
