import { NextRequest, NextResponse } from "next/server";
import { getServiceSupabase } from "@/lib/supabase-server";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ date: string }> }
) {
  try {
    const { date } = await params;
    const deviceId = request.nextUrl.searchParams.get("device");

    const supabase = getServiceSupabase();

    let query = supabase
      .from("daily_stats")
      .select("date, total_events, unique_apps, top_apps, hourly_breakdown")
      .eq("date", date);

    if (deviceId) {
      query = query.eq("device_id", deviceId);
    }

    const { data, error } = await query.limit(1).single();

    if (error) {
      if (error.code === "PGRST116") {
        // No rows found
        return NextResponse.json(
          { error: "No data for this date" },
          { status: 404 }
        );
      }
      throw error;
    }

    return NextResponse.json({
      date: data.date,
      total_events: data.total_events || 0,
      unique_apps: data.unique_apps || 0,
      top_apps: data.top_apps || [],
      hourly_breakdown: data.hourly_breakdown || [],
    });
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : "Unknown error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
