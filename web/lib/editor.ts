import "server-only";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { ENGINE_URL } from "./api";

export const TOKEN_COOKIE = "marsad_token";

export async function editorFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = (await cookies()).get(TOKEN_COOKIE)?.value;
  if (!token) redirect("/editor/login");
  const res = await fetch(`${ENGINE_URL}${path}`, {
    ...init,
    cache: "no-store",
    headers: { "content-type": "application/json", ...(init.headers ?? {}), authorization: `Bearer ${token}` },
  });
  if (res.status === 401) redirect("/editor/login?expired=1");
  if (!res.ok) {
    let detail = `${res.status}`;
    try { detail = (await res.json()).detail ?? detail; } catch { /* keep status */ }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json() as Promise<T>;
}
