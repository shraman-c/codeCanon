import { NextResponse } from "next/server";

export async function GET(_request: Request, { params }: { params: { id: string } }) {
  const { id } = await params;
  return NextResponse.json({ id, user: null });
}
