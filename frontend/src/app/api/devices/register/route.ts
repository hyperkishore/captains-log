import { NextRequest, NextResponse } from "next/server";
import { getServiceSupabase } from "@/lib/supabase-server";

export async function POST(request: NextRequest) {
  try {
    const { device_id, name } = await request.json();
    if (!device_id) {
      return NextResponse.json({ error: "device_id required" }, { status: 400 });
    }

    const supabase = getServiceSupabase();

    const { error } = await supabase
      .from("devices")
      .upsert(
        { id: device_id, name: name || null, last_sync: new Date().toISOString() },
        { onConflict: "id" }
      );

    if (error) throw error;

    return NextResponse.json({ status: "registered", device_id });
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : "Unknown error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
