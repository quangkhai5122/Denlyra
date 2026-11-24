/** Local-only synthetic demo proxy: NOT authenticated for production use. */
import { NextRequest, NextResponse } from "next/server";

type Ctx = { params: Promise<{ path: string[] }> };

async function forward(req: NextRequest, ctx: Ctx): Promise<Response> {
  if (process.env.DENLYRA_DEMO_MODE !== "1") {
    return NextResponse.json({ detail: "Demo proxy disabled" }, { status: 403 });
  }
  const base = process.env.DENLYRA_DEMO_API ?? "http://127.0.0.1:8766";
  const parsed = new URL(base);
  if (parsed.protocol !== "http:" || !["127.0.0.1", "localhost"].includes(parsed.hostname)) {
    return NextResponse.json({ detail: "Only loopback API is supported" }, { status: 403 });
  }
  const { path } = await ctx.params;
  const safe = path.map(encodeURIComponent).join("/");
  const target = `${parsed.origin}/api/v1/${safe}${req.nextUrl.search}`;
  const headers: Record<string, string> = { "Accept": "application/json" };
  const clinic = req.headers.get("X-Demo-Clinic");
  if (clinic) headers["X-Demo-Clinic"] = clinic;
  const auth = req.headers.get("Authorization");
  if (auth) headers["Authorization"] = auth;
  const secFetchSite = req.headers.get("sec-fetch-site");
  if (secFetchSite) headers["Sec-Fetch-Site"] = secFetchSite;
  const origin = req.headers.get("origin");
  if (origin) {
    headers["Origin"] = origin === req.nextUrl.origin ? parsed.origin : origin;
  }
  headers["X-Demo-Actor"] = "nextjs-prototype-user";
  if (!["GET", "HEAD"].includes(req.method)) headers["Content-Type"] = "application/json";
  try {
    const response = await fetch(target, {
      method: req.method,
      headers,
      body: ["GET", "HEAD"].includes(req.method) ? undefined : await req.text(),
      cache: "no-store",
      redirect: "error",
    });
    const body = await response.text();
    return new Response(body, {status: response.status, headers: {
      "Content-Type": response.headers.get("Content-Type") || "application/json",
      "Cache-Control": "no-store",
      "X-Denlyra-Demo-Only": "true",
    }});
  } catch {
    return NextResponse.json({ detail: "Local demo backend unavailable" }, { status: 503 });
  }
}

export { forward as GET, forward as POST, forward as PUT, forward as DELETE };
