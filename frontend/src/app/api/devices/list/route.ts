import { NextResponse } from "next/server";
import { getServiceSupabase } from "@/lib/supabase-server";
import { getAuthenticatedUser } from "@/lib/supabase-auth";

export async function GET() {
  try {
    const user = await getAuthenticatedUser();

    if (!user || !user.email) {
      return NextResponse.json(
        { error: "Authentication required" },
        { status: 401 }
      );
    }

    const supabase = getServiceSupabase();

    const { data, error } = await supabase
      .from("devices")
      .select("id, name, last_sync, created_at")
      .eq("user_email", user.email)
      .order("last_sync", { ascending: false });

    if (error) throw error;

    return NextResponse.json({ devices: data || [] });
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : "Unknown error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
