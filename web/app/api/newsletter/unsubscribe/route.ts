import { engine } from "@/lib/api";

// RFC 8058 one-click unsubscribe: mail clients POST here from the List-Unsubscribe header.
export async function POST(request: Request) {
  const token = new URL(request.url).searchParams.get("token") ?? "";
  const { status } = await engine("/api/unsubscribe", { method: "POST", body: JSON.stringify({ token }) });
  return new Response(status === 200 ? "unsubscribed" : "unknown token", { status: status === 200 ? 200 : 404 });
}
