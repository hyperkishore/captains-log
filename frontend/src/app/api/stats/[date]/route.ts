import { NextRequest, NextResponse } from "next/server";
import { getServiceSupabase } from "@/lib/supabase-server";
import { getUserDeviceIds } from "@/lib/supabase-auth";

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
      .select("date, total_events, unique_apps, top_apps, hourly_breakdown, time_blocks, categories")
      .eq("date", date);

    if (deviceId) {
      query = query.eq("device_id", deviceId);
    } else {
      const deviceIds = await getUserDeviceIds();
      if (!deviceIds) {
        return NextResponse.json(
          { error: "Authentication required" },
          { status: 401 }
        );
      }
      if (deviceIds.length === 0) {
        return NextResponse.json(
          { error: "No devices linked to your account" },
          { status: 404 }
        );
      }
      query = query.in("device_id", deviceIds);
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

    // Calculate tracked minutes from time_blocks (sum of all category counts * 5 min per block)
    // Each time_block.total represents event count in that hour, use as proxy for active minutes
    const timeBlocks = data.time_blocks || [];
    const categories = data.categories || {};

    // Estimate tracked hours: each event represents ~2 min of activity (avg time between switches)
    const trackedMinutes = Math.round(data.total_events * 2);

    return NextResponse.json({
      date: data.date,
      total_events: data.total_events || 0,
      unique_apps: data.unique_apps || 0,
      top_apps: data.top_apps || [],
      hourly_breakdown: data.hourly_breakdown || [],
      tracked_minutes: trackedMinutes,
      categories,
    });
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : "Unknown error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
