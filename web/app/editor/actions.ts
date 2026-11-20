"use server";
import { cookies } from "next/headers";
import { revalidatePath, revalidateTag } from "next/cache";
import { redirect } from "next/navigation";
import { ENGINE_URL } from "@/lib/api";
import { TOKEN_COOKIE, editorFetch } from "@/lib/editor";
import type { ApiClientRow, EditorDossier, EditorItem, QueueRow } from "@/lib/types";

export type ActionResult = { ok: boolean; message: string; item?: EditorItem; email?: string } | null;

export async function login(_prev: ActionResult, form: FormData): Promise<ActionResult> {
  const res = await fetch(`${ENGINE_URL}/api/editor/login`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email: form.get("email"), password: form.get("password") }),
  });
  if (!res.ok) return { ok: false, message: "البريد الإلكتروني أو كلمة المرور غير صحيحة.", email: String(form.get("email") ?? "") };
  const { token } = await res.json();
  (await cookies()).set(TOKEN_COOKIE, token, {
    httpOnly: true, sameSite: "lax", secure: process.env.NODE_ENV === "production", path: "/", maxAge: 60 * 60 * 24 * 14,
  });
  redirect("/editor");
}

export async function logout() {
  await editorFetch("/api/editor/logout", { method: "POST" }).catch(() => null);
  (await cookies()).delete(TOKEN_COOKIE);
  redirect("/editor/login");
}

async function run(fn: () => Promise<EditorItem>, message: string, touchesPublic = false): Promise<ActionResult> {
  try {
    const item = await fn();
    if (touchesPublic) {
      revalidateTag("public");
      revalidatePath("/", "layout");
    }
    return { ok: true, message, item };
  } catch (e) {
    if (e && typeof e === "object" && "digest" in e) throw e; // let redirect() propagate
    return { ok: false, message: e instanceof Error ? e.message : "تعذّر تنفيذ الإجراء." };
  }
}

export async function saveItem(id: number, patch: Record<string, unknown>, published: boolean): Promise<ActionResult> {
  return run(() => editorFetch<EditorItem>(`/api/editor/items/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
    "حُفظت التعديلات.", published);
}

export async function itemAction(id: number, action: "publish" | "reject" | "unpublish" | "retry", reason = ""): Promise<ActionResult> {
  const labels = { publish: "نُشرت المادة.", reject: "رُفضت المادة.", unpublish: "أُزيلت المادة من الموقع.", retry: "أُعيدت المادة إلى خط المعالجة." };
  return run(() => editorFetch<EditorItem>(`/api/editor/items/${id}/${action}`, { method: "POST", body: JSON.stringify({ reason }) }),
    labels[action], action === "publish" || action === "unpublish");
}

export async function retranslate(id: number, index: number): Promise<{ ok: boolean; ar?: string; message?: string }> {
  try {
    const r = await editorFetch<{ ar: string }>(`/api/editor/items/${id}/paragraphs/${index}/retranslate`, { method: "POST" });
    return { ok: true, ar: r.ar };
  } catch (e) {
    if (e && typeof e === "object" && "digest" in e) throw e;
    return { ok: false, message: e instanceof Error ? e.message : "تعذّرت إعادة الترجمة." };
  }
}

export async function upsertTerm(form: FormData) {
  await editorFetch("/api/editor/glossary", {
    method: "POST",
    body: JSON.stringify({
      term_en: form.get("term_en"),
      term_ar: form.get("term_ar"),
      variants_ar: String(form.get("variants_ar") ?? "").split(/[،,]/).map((v) => v.trim()).filter(Boolean),
      definition_ar: form.get("definition_ar") ?? "",
      domain: form.get("domain") || "general",
      status: form.get("status") || "approved",
    }),
  });
  revalidateTag("public");
  revalidatePath("/editor/glossary");
}

export async function deleteTerm(form: FormData) {
  await editorFetch(`/api/editor/glossary/${form.get("id")}`, { method: "DELETE" });
  revalidatePath("/editor/glossary");
}

export async function resolveFeedback(form: FormData) {
  await editorFetch(`/api/editor/feedback/${form.get("id")}/resolve`, { method: "POST" });
  revalidatePath("/editor/feedback");
}

export async function importItem(_prev: ActionResult, form: FormData): Promise<ActionResult> {
  let id: number;
  try {
    const r = await editorFetch<{ id: number }>("/api/editor/import", {
      method: "POST",
      body: JSON.stringify({ url: form.get("url"), source_slug: form.get("source_slug"), title: form.get("title") ?? "" }),
    });
    id = r.id;
  } catch (e) {
    if (e && typeof e === "object" && "digest" in e) throw e;
    return { ok: false, message: e instanceof Error ? e.message : "تعذّر الاستيراد." };
  }
  redirect(`/editor/items/${id}`);
}

export async function setLicense(id: number, license: string, evidence: string): Promise<ActionResult> {
  return run(() => editorFetch<EditorItem>(`/api/editor/items/${id}/license`, {
    method: "POST", body: JSON.stringify({ license, evidence }),
  }), "سُجّل الترخيص، وأُعيدت المادة إلى خط المعالجة لترجمة نصها الكامل.");
}

export async function createDigest() {
  const r = await editorFetch<{ id: number }>("/api/editor/digests", { method: "POST" }).catch((e: Error) => {
    if (e && typeof e === "object" && "digest" in e) throw e;
    return { id: 0, error: e.message };
  });
  if ("error" in r) redirect(`/editor/newsletter?error=${encodeURIComponent(String(r.error))}`);
  redirect(`/editor/newsletter/${r.id}`);
}

export async function saveDigest(id: number, form: FormData) {
  await editorFetch(`/api/editor/digests/${id}`, {
    method: "PATCH",
    body: JSON.stringify({
      subject_ar: form.get("subject_ar"), intro_ar: form.get("intro_ar"),
      document_ids: form.getAll("document_ids").map(Number),
    }),
  });
  revalidatePath(`/editor/newsletter/${id}`);
}

export async function sendDigest(id: number) {
  await editorFetch(`/api/editor/digests/${id}/send`, { method: "POST" });
  revalidatePath("/editor/newsletter");
  redirect("/editor/newsletter");
}

// ---------------------------------------------------------------- phase 3

export async function createDossier(form: FormData) {
  const d = await editorFetch<EditorDossier>("/api/editor/dossiers", {
    method: "POST", body: JSON.stringify({ title_ar: form.get("title_ar") }),
  });
  redirect(`/editor/dossiers/${d.id}`);
}

type DossierResult = { ok: boolean; message: string; dossier?: EditorDossier };

async function dossierCall(fn: () => Promise<EditorDossier>, message: string): Promise<DossierResult> {
  try {
    const dossier = await fn();
    revalidateTag("public");
    return { ok: true, message, dossier };
  } catch (e) {
    if (e && typeof e === "object" && "digest" in e) throw e;
    return { ok: false, message: e instanceof Error ? e.message : "تعذّر تنفيذ الإجراء." };
  }
}

export async function saveDossier(id: number, patch: Record<string, unknown>) {
  return dossierCall(() => editorFetch<EditorDossier>(`/api/editor/dossiers/${id}`, { method: "PATCH", body: JSON.stringify(patch) }), "حُفظ الملف.");
}

export async function dossierAction(id: number, action: "publish" | "unpublish" | "draft-intro") {
  const msg = { publish: "نُشر الملف.", unpublish: "أُخفي الملف من الموقع.", "draft-intro": "كُتبت مقدمة مقترحة. راجعها واحفظها قبل النشر." }[action];
  return dossierCall(() => editorFetch<EditorDossier>(`/api/editor/dossiers/${id}/${action}`, { method: "POST" }), msg);
}

export async function dossierSuggestions(id: number, q: string): Promise<QueueRow[]> {
  return editorFetch<QueueRow[]>(`/api/editor/dossiers/${id}/suggestions?q=${encodeURIComponent(q)}`);
}

export async function draftTrend(month: string) {
  await editorFetch(`/api/editor/trends/${month}/draft`, { method: "POST" }).catch((e: Error) => {
    if (e && typeof e === "object" && "digest" in e) throw e;
    redirect(`/editor/trends/${month}?error=${encodeURIComponent(e.message)}`);
  });
  revalidatePath(`/editor/trends/${month}`);
}

export async function saveTrend(month: string, form: FormData) {
  await editorFetch(`/api/editor/trends/${month}`, { method: "PATCH", body: JSON.stringify({ narrative_ar: form.get("narrative_ar") }) });
  revalidatePath(`/editor/trends/${month}`);
}

export async function publishTrend(month: string) {
  await editorFetch(`/api/editor/trends/${month}/publish`, { method: "POST" }).catch((e: Error) => {
    if (e && typeof e === "object" && "digest" in e) throw e;
    redirect(`/editor/trends/${month}?error=${encodeURIComponent(e.message)}`);
  });
  revalidateTag("public");
  revalidatePath(`/editor/trends/${month}`);
}

export type KeyState = { ok: boolean; message: string; client?: ApiClientRow } | null;

export async function createApiClient(_: KeyState, form: FormData): Promise<KeyState> {
  try {
    const client = await editorFetch<ApiClientRow>("/api/editor/api-clients", {
      method: "POST",
      body: JSON.stringify({ name: form.get("name"), organization: form.get("organization") ?? "",
                             contact_email: form.get("contact_email") ?? "", rate_limit_per_minute: Number(form.get("rate_limit") || 60) }),
    });
    revalidatePath("/editor/api-clients");
    return { ok: true, message: "أُصدر المفتاح.", client };
  } catch (e) {
    if (e && typeof e === "object" && "digest" in e) throw e;
    return { ok: false, message: e instanceof Error ? e.message : "تعذّر إصدار المفتاح." };
  }
}

export async function setApiClientActive(id: number, active: boolean) {
  await editorFetch(`/api/editor/api-clients/${id}`, { method: "PATCH", body: JSON.stringify({ is_active: active }) });
  revalidatePath("/editor/api-clients");
}
