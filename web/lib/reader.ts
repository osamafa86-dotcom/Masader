import "server-only";
import { cookies } from "next/headers";
import { ENGINE_URL } from "./api";

export const READER_COOKIE = "marsad_reader";

/** Calls the engine on behalf of the signed-in reader; returns status 401 when signed out. */
export async function readerFetch<T>(path: string, init: RequestInit = {}): Promise<{ status: number; data: T | null }> {
  const token = (await cookies()).get(READER_COOKIE)?.value;
  if (!token) return { status: 401, data: null };
  const res = await fetch(`${ENGINE_URL}${path}`, {
    ...init, cache: "no-store",
    headers: { "content-type": "application/json", ...(init.headers ?? {}), "x-reader-token": token },
  });
  let data: T | null = null;
  try { data = (await res.json()) as T; } catch { /* empty */ }
  return { status: res.status, data };
}
