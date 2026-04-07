import { NextRequest, NextResponse } from "next/server";
import { getServiceSupabase } from "@/lib/supabase-server";

interface TimeBlock {
  hour: number;
  categories: Record<string, number>;
  total: number;
  primary_category: string;
}

interface Summary {
  primary_app: string | null;
  activity_type: string | null;
  focus_score: number | null;
  key_activities: string[] | null;
  context: string | null;
  context_switches: number | null;
  period_start: string;
  period_end: string;
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ date: string }> }
) {
  try {
    const { date } = await params;
    const deviceId = request.nextUrl.searchParams.get("device");

    const supabase = getServiceSupabase();

    // Fetch daily_stats
    let statsQuery = supabase
      .from("daily_stats")
      .select(
        "total_events, top_apps, time_blocks, categories, focus_data, hourly_breakdown"
      )
      .eq("date", date);

    if (deviceId) {
      statsQuery = statsQuery.eq("device_id", deviceId);
    }

    const { data: statsData } = await statsQuery.limit(1).single();

    // Fetch summaries for this date
    const dayStart = `${date}T00:00:00Z`;
    const dayEnd = `${date}T23:59:59Z`;

    let summariesQuery = supabase
      .from("synced_summaries")
      .select(
        "primary_app, activity_type, focus_score, key_activities, context, context_switches, period_start, period_end"
      )
      .gte("period_start", dayStart)
      .lte("period_start", dayEnd);

    if (deviceId) {
      summariesQuery = summariesQuery.eq("device_id", deviceId);
    }

    const { data: summariesData } = await summariesQuery;

    if (!statsData && (!summariesData || summariesData.length === 0)) {
      return NextResponse.json(
        { error: "No data for this date" },
        { status: 404 }
      );
    }

    // Build metrics from stats
    const totalEvents = statsData?.total_events || 0;
    const timeBlocks: TimeBlock[] = statsData?.time_blocks || [];
    const summaries: Summary[] = summariesData || [];

    // Calculate context switches from summaries
    const contextSwitches = summaries.reduce(
      (sum, s) => sum + (s.context_switches || 0),
      0
    );

    // Calculate average focus score from summaries
    const focusScores = summaries
      .map((s) => s.focus_score)
      .filter((s): s is number => s !== null);
    const avgFocusScore =
      focusScores.length > 0
        ? Math.round(
            focusScores.reduce((a, b) => a + b, 0) / focusScores.length
          )
        : 0;

    // Calculate deep work minutes (periods with focus_score >= 7)
    const deepWorkSummaries = summaries.filter(
      (s) => s.focus_score !== null && s.focus_score >= 7
    );
    const deepWorkMinutes = deepWorkSummaries.reduce((sum, s) => {
      const start = new Date(s.period_start).getTime();
      const end = new Date(s.period_end).getTime();
      return sum + (end - start) / 60000;
    }, 0);

    // Determine top category from time blocks
    const categoryTotals: Record<string, number> = {};
    timeBlocks.forEach((block) => {
      if (block.categories) {
        Object.entries(block.categories).forEach(([cat, count]) => {
          categoryTotals[cat] = (categoryTotals[cat] || 0) + (count as number);
        });
      }
    });
    const topCategory =
      Object.entries(categoryTotals).sort((a, b) => b[1] - a[1])[0]?.[0] ||
      "Unknown";

    // Calculate productive hours: each event ~2 min of activity
    const productiveHours = Math.round((totalEvents * 2) / 60 * 10) / 10;

    // Build narrative from summaries
    const contexts = summaries
      .map((s) => s.context)
      .filter((c): c is string => c !== null && c.length > 0);
    const narrative =
      contexts.length > 0
        ? contexts.slice(0, 3).join(". ") + "."
        : `Tracked ${totalEvents} events across the day. Primary focus: ${topCategory}.`;

    // Build wins
    const wins: { title: string; description: string }[] = [];
    if (deepWorkMinutes >= 60) {
      wins.push({
        title: `${Math.round(deepWorkMinutes / 60 * 10) / 10} hours of deep work`,
        description: "Sustained focus on high-value tasks",
      });
    }
    if (avgFocusScore >= 7) {
      wins.push({
        title: `Focus score: ${avgFocusScore}/10`,
        description: "High concentration throughout the day",
      });
    }
    if (contextSwitches < 30 && totalEvents > 0) {
      wins.push({
        title: `Only ${contextSwitches} context switches`,
        description: "Minimal task switching - good flow state",
      });
    }

    // Build improvements
    const improvements: {
      title: string;
      description: string;
      severity: string;
    }[] = [];
    if (avgFocusScore > 0 && avgFocusScore < 5) {
      improvements.push({
        title: "Low focus score",
        description:
          "Consider blocking distractions during deep work sessions",
        severity: "warning",
      });
    }
    if (contextSwitches > 50) {
      improvements.push({
        title: `High context switching (${contextSwitches})`,
        description: "Try batching similar tasks together",
        severity: "warning",
      });
    }

    return NextResponse.json({
      narrative,
      metrics: {
        total_events: totalEvents,
        context_switches: contextSwitches,
        deep_work_minutes: Math.round(deepWorkMinutes),
        focus_score: avgFocusScore,
        productive_hours: productiveHours,
        top_category: topCategory,
      },
      wins,
      improvements,
      recommendations: [],
    });
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : "Unknown error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
