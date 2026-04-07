import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { getServiceSupabase } from "@/lib/supabase-server";

export async function getAuthenticatedUser() {
  const cookieStore = await cookies();
  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value, options }) => {
            cookieStore.set(name, value, options);
          });
        },
      },
    }
  );
  const {
    data: { user },
  } = await supabase.auth.getUser();
  return user;
}

/**
 * Get the device IDs belonging to the authenticated user.
 * Returns null if no user is authenticated.
 */
export async function getUserDeviceIds(): Promise<string[] | null> {
  const user = await getAuthenticatedUser();
  if (!user || !user.email) return null;

  const supabase = getServiceSupabase();
  const { data, error } = await supabase
    .from("devices")
    .select("id")
    .eq("user_email", user.email);

  if (error) throw error;

  return (data || []).map((d) => d.id);
}
