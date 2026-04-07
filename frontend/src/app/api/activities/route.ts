import { NextRequest, NextResponse } from "next/server";
import { getServiceSupabase } from "@/lib/supabase-server";
import { getUserDeviceIds } from "@/lib/supabase-auth";

export async function GET(request: NextRequest) {
  try {
    const date = request.nextUrl.searchParams.get("date");
    const limit = parseInt(request.nextUrl.searchParams.get("limit") || "500");
    const deviceId = request.nextUrl.searchParams.get("device");

    if (!date) {
      return NextResponse.json(
        { error: "date parameter required" },
        { status: 400 }
      );
    }

    const supabase = getServiceSupabase();

    const dayStart = `${date}T00:00:00Z`;
    const dayEnd = `${date}T23:59:59Z`;

    let query = supabase
      .from("synced_activities")
      .select(
        "timestamp, app_name, bundle_id, window_title, url, idle_seconds, idle_status"
      )
      .gte("timestamp", dayStart)
      .lte("timestamp", dayEnd)
      .order("timestamp", { ascending: false })
      .limit(limit);

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
        return NextResponse.json([], { status: 200 });
      }
      query = query.in("device_id", deviceIds);
    }

    const { data, error } = await query;

    if (error) {
      throw error;
    }

    // Transform to match the Activity type the frontend expects
    const activities = (data || []).map((row, index) => ({
      id: index,
      timestamp: row.timestamp,
      app_name: row.app_name,
      bundle_id: row.bundle_id || null,
      window_title: row.window_title || null,
      url: row.url || null,
      idle_seconds: row.idle_seconds || 0,
      idle_status: row.idle_status || "ACTIVE",
    }));

    return NextResponse.json(activities);
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : "Unknown error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
