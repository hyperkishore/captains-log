import { NextRequest, NextResponse } from "next/server";
import { getServiceSupabase } from "@/lib/supabase-server";

export async function POST(request: NextRequest) {
  try {
    const { device_id, activities } = await request.json();
    if (!device_id || !activities) {
      return NextResponse.json({ error: "device_id and activities required" }, { status: 400 });
    }

    const supabase = getServiceSupabase();

    // Insert activities in batch
    const rows = activities.map((a: Record<string, unknown>) => ({
      device_id,
      timestamp: a.timestamp,
      app_name: a.app_name,
      bundle_id: a.bundle_id || null,
      window_title: a.window_title || null,
      url: a.url || null,
      idle_seconds: a.idle_seconds || null,
      idle_status: a.idle_status || null,
      work_category: a.work_category || null,
    }));

    const { error } = await supabase.from("synced_activities").insert(rows);
    if (error) throw error;

    // Update device last_sync
    await supabase
      .from("devices")
      .update({ last_sync: new Date().toISOString() })
      .eq("id", device_id);

    return NextResponse.json({ status: "synced", count: rows.length });
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : "Unknown error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
