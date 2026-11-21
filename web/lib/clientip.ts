import "server-only";
import { headers } from "next/headers";

/** Forwards the reader's address (set by Caddy) so the engine can apply per-address limits. */
export async function clientHeaders(): Promise<Record<string, string>> {
  try {
    const h = await headers();
    const ip = (h.get("x-forwarded-for") ?? "").split(",")[0].trim() || h.get("x-real-ip") || "";
    return ip ? { "x-client-ip": ip } : {};
  } catch {
    return {}; // outside a request (build time)
  }
}
