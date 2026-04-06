import { NextResponse } from "next/server";

export function GET() {
  return NextResponse.json({ status: "ok", service: "Captain's Log Cloud API" });
}
