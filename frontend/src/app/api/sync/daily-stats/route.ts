import { NextRequest, NextResponse } from "next/server";
import { getServiceSupabase } from "@/lib/supabase-server";

export async function POST(request: NextRequest) {
  try {
    const data = await request.json();
    const { device_id, date, total_events, unique_apps, top_apps, hourly_breakdown, time_blocks, categories, focus_data } = data;

    if (!device_id || !date) {
      return NextResponse.json({ error: "device_id and date required" }, { status: 400 });
    }

    const supabase = getServiceSupabase();

    // Upsert daily stats
    const { error } = await supabase
      .from("daily_stats")
      .upsert(
        {
          device_id,
          date,
          total_events,
          unique_apps,
          top_apps,
          hourly_breakdown,
          time_blocks,
          categories,
          focus_data,
          updated_at: new Date().toISOString(),
        },
        { onConflict: "device_id,date" }
      );

    if (error) throw error;

    // Update device last_sync
    await supabase
      .from("devices")
      .update({ last_sync: new Date().toISOString() })
      .eq("id", device_id);

    return NextResponse.json({ status: "synced", date });
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : "Unknown error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
