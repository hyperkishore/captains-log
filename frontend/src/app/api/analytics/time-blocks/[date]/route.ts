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
      .select("time_blocks")
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
        return NextResponse.json([], { status: 200 });
      }
      query = query.in("device_id", deviceIds);
    }

    const { data, error } = await query.limit(1).single();

    if (error) {
      if (error.code === "PGRST116") {
        return NextResponse.json([], { status: 200 });
      }
      throw error;
    }

    return NextResponse.json(data.time_blocks || []);
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : "Unknown error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
