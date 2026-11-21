"use server";
import { engine } from "@/lib/api";
import type { Subscription } from "@/lib/types";

export type NlState = { ok: boolean; message: string; sub?: Subscription } | null;

const list = (form: FormData, key: string) => form.getAll(key).map(String).filter(Boolean);
const keywords = (form: FormData) => String(form.get("keywords") ?? "").split(/[،,\n]/).map((k) => k.trim()).filter(Boolean);

export async function subscribeAction(_: NlState, form: FormData): Promise<NlState> {
  const { status, data } = await engine<{ message?: string; detail?: string }>("/api/subscribe", {
    method: "POST",
    body: JSON.stringify({ email: form.get("email"), topics: list(form, "topics"), sources: list(form, "sources"), keywords: keywords(form) }),
  });
  if (status === 202) return { ok: true, message: data?.message ?? "تحقق من بريدك لتأكيد الاشتراك." };
  if (status === 422) return { ok: false, message: "اكتب بريداً إلكترونياً صحيحاً." };
  if (status === 503) return { ok: false, message: "النشرة البريدية لم تُفعّل بعد. عد إلينا قريباً." };
  if (status === 429) return { ok: false, message: "طلبات كثيرة من عنوانك. حاول مجدداً بعد ساعة." };
  return { ok: false, message: "تعذّر إرسال رسالة التأكيد الآن. حاول مجدداً بعد قليل." };
}

async function withToken(path: string, token: string, method: string, body?: object): Promise<NlState> {
  const { status, data } = await engine<Subscription>(path, { method, body: JSON.stringify(body ?? { token }) });
  if (status === 404) return { ok: false, message: "الرابط غير صالح أو منتهٍ. اشترك من جديد إن أردت." };
  if (status !== 200 || !data) return { ok: false, message: "تعذّر تنفيذ الطلب. حاول مجدداً بعد قليل." };
  return { ok: true, message: "", sub: data };
}

export async function confirmAction(_: NlState, form: FormData): Promise<NlState> {
  const r = await withToken("/api/subscribe/confirm", String(form.get("token")), "POST");
  return r?.ok ? { ...r, message: "تأكد اشتراكك. ستصلك النشرة القادمة." } : r;
}

export async function unsubscribeAction(_: NlState, form: FormData): Promise<NlState> {
  const r = await withToken("/api/unsubscribe", String(form.get("token")), "POST");
  return r?.ok ? { ...r, message: "ألغينا اشتراكك ولن تصلك رسائل أخرى. يمكنك الاشتراك مجدداً في أي وقت." } : r;
}

export async function savePrefsAction(_: NlState, form: FormData): Promise<NlState> {
  const token = String(form.get("token"));
  const r = await withToken(`/api/subscription/${encodeURIComponent(token)}`, token, "PUT",
    { topics: list(form, "topics"), sources: list(form, "sources"), keywords: keywords(form) });
  return r?.ok ? { ...r, message: "حُفظت اختياراتك." } : r;
}
