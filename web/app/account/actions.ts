"use server";
import { cookies } from "next/headers";
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { engine } from "@/lib/api";
import { READER_COOKIE, readerFetch } from "@/lib/reader";

export type AccState = { ok: boolean; message: string } | null;

export async function requestLink(_: AccState, form: FormData): Promise<AccState> {
  const { status } = await engine("/api/account/login", { method: "POST", body: JSON.stringify({ email: form.get("email") }) });
  if (status === 202) return { ok: true, message: "إن كان البريد صحيحاً فسيصلك رابط الدخول خلال دقائق. الرابط صالح 20 دقيقة." };
  if (status === 422) return { ok: false, message: "اكتب بريداً إلكترونياً صحيحاً." };
  if (status === 503) return { ok: false, message: "الحسابات غير مفعّلة بعد على هذا الموقع." };
  if (status === 429) return { ok: false, message: "طلبات كثيرة من عنوانك. حاول مجدداً بعد ساعة." };
  return { ok: false, message: "تعذّر إرسال الرابط الآن. حاول مجدداً بعد قليل." };
}

export async function verifyLink(_: AccState, form: FormData): Promise<AccState> {
  const { status, data } = await engine<{ session_token: string }>("/api/account/verify", {
    method: "POST", body: JSON.stringify({ token: form.get("token") }),
  });
  if (status !== 200 || !data) return { ok: false, message: "رابط الدخول غير صالح أو استُخدم من قبل أو انتهت مدته. اطلب رابطاً جديداً." };
  (await cookies()).set(READER_COOKIE, data.session_token, {
    httpOnly: true, sameSite: "lax", secure: process.env.NODE_ENV === "production", path: "/", maxAge: 60 * 60 * 24 * 30,
  });
  redirect("/account");
}

export async function logout() {
  await readerFetch("/api/account/logout", { method: "POST" });
  (await cookies()).delete(READER_COOKIE);
  redirect("/");
}

export async function toggleSaved(docId: number, save: boolean): Promise<{ ok: boolean; saved: boolean; signedOut?: boolean }> {
  const { status } = await readerFetch(`/api/account/library/${docId}`, save
    ? { method: "PUT", body: JSON.stringify({ note: "" }) } : { method: "DELETE" });
  if (status === 401) return { ok: false, saved: !save, signedOut: true };
  revalidatePath("/account");
  return { ok: status === 200, saved: status === 200 ? save : !save };
}

export async function saveNote(docId: number, form: FormData) {
  await readerFetch(`/api/account/library/${docId}`, { method: "PUT", body: JSON.stringify({ note: form.get("note") ?? "" }) });
  revalidatePath("/account");
}

export async function removeSaved(docId: number) {
  await readerFetch(`/api/account/library/${docId}`, { method: "DELETE" });
  revalidatePath("/account");
}

export async function saveAlerts(_: AccState, form: FormData): Promise<AccState> {
  const keywords = String(form.get("keywords") ?? "").split(/[،,\n]/).map((k) => k.trim()).filter(Boolean);
  const { status } = await readerFetch("/api/account/alerts", {
    method: "PUT",
    body: JSON.stringify({ active: form.get("active") === "on", topics: form.getAll("topics").map(String),
                           sources: form.getAll("sources").map(String), keywords }),
  });
  if (status === 401) redirect("/account/login");
  return status === 200 ? { ok: true, message: "حُفظت إعدادات التنبيه." } : { ok: false, message: "تعذّر الحفظ. حاول مجدداً." };
}

export async function deleteAccount() {
  await readerFetch("/api/account", { method: "DELETE" });
  (await cookies()).delete(READER_COOKIE);
  redirect("/?account=deleted");
}
