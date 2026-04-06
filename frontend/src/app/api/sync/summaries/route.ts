import { NextRequest, NextResponse } from "next/server";
import { getServiceSupabase } from "@/lib/supabase-server";

export async function POST(request: NextRequest) {
  try {
    const { device_id, summaries } = await request.json();
    if (!device_id || !summaries) {
      return NextResponse.json({ error: "device_id and summaries required" }, { status: 400 });
    }

    const supabase = getServiceSupabase();

    const rows = summaries.map((s: Record<string, unknown>) => ({
      device_id,
      period_start: s.period_start,
      period_end: s.period_end,
      primary_app: s.primary_app || null,
      activity_type: s.activity_type || null,
      focus_score: s.focus_score || null,
      key_activities: s.key_activities || null,
      context: s.context || null,
      context_switches: s.context_switches || null,
    }));

    const { error } = await supabase.from("synced_summaries").insert(rows);
    if (error) throw error;

    return NextResponse.json({ status: "synced", count: rows.length });
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : "Unknown error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
