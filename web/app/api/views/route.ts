import { ENGINE_URL } from "@/lib/api";

export async function POST(request: Request) {
  const body = await request.text();
  const ip = (request.headers.get("x-forwarded-for") ?? "").split(",")[0].trim();
  await fetch(`${ENGINE_URL}/api/views`, {
    method: "POST",
    headers: { "content-type": "application/json", "x-client-ua": request.headers.get("user-agent") ?? "",
               ...(ip ? { "x-client-ip": ip } : {}) },
    body: body.slice(0, 200),
  }).catch(() => undefined);
  return new Response(null, { status: 204 });
}
