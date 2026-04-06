import { NextRequest, NextResponse } from "next/server";
import { getServiceSupabase } from "@/lib/supabase-server";

interface TopApp {
  app_name: string;
  count: number;
}

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
      .select("top_apps")
      .eq("date", date);

    if (deviceId) {
      query = query.eq("device_id", deviceId);
    }

    const { data, error } = await query.limit(1).single();

    if (error) {
      if (error.code === "PGRST116") {
        return NextResponse.json(
          { top_apps: [], rest_apps: [], top_percent: 0, ratio: "0/0" },
          { status: 200 }
        );
      }
      throw error;
    }

    const topApps: TopApp[] = data.top_apps || [];
    if (topApps.length === 0) {
      return NextResponse.json({
        top_apps: [],
        rest_apps: [],
        top_percent: 0,
        ratio: "0/0",
      });
    }

    // Sort by count descending
    const sorted = [...topApps].sort((a, b) => b.count - a.count);
    const totalCount = sorted.reduce((sum, app) => sum + app.count, 0);

    // Find the top 20% of apps (by count of unique apps)
    const top20Count = Math.max(1, Math.ceil(sorted.length * 0.2));
    const topSlice = sorted.slice(0, top20Count);
    const restSlice = sorted.slice(top20Count);

    // Build pareto arrays with cumulative percentages
    let cumulative = 0;
    const topAppsResult = topSlice.map((app) => {
      const percent = totalCount > 0 ? (app.count / totalCount) * 100 : 0;
      cumulative += percent;
      return {
        app: app.app_name,
        count: app.count,
        percent: Math.round(percent * 10) / 10,
        cumulative_percent: Math.round(cumulative * 10) / 10,
      };
    });

    const restAppsResult = restSlice.map((app) => {
      const percent = totalCount > 0 ? (app.count / totalCount) * 100 : 0;
      cumulative += percent;
      return {
        app: app.app_name,
        count: app.count,
        percent: Math.round(percent * 10) / 10,
        cumulative_percent: Math.round(cumulative * 10) / 10,
      };
    });

    const topPercent = Math.round((top20Count / sorted.length) * 100);

    return NextResponse.json({
      top_apps: topAppsResult,
      rest_apps: restAppsResult,
      top_percent: topPercent,
      ratio: `${top20Count}/${sorted.length}`,
    });
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : "Unknown error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
