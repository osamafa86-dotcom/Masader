"use server";
import { ENGINE_URL } from "@/lib/api";
import { clientHeaders } from "@/lib/clientip";

export type FeedbackState = { ok: boolean; message: string } | null;

export async function sendFeedback(_prev: FeedbackState, form: FormData): Promise<FeedbackState> {
  const message = String(form.get("message") ?? "").trim();
  if (message.length < 3) return { ok: false, message: "اكتب وصفاً قصيراً للخطأ قبل الإرسال." };
  const paragraph = form.get("paragraph_index");
  const res = await fetch(`${ENGINE_URL}/api/feedback`, {
    method: "POST",
    headers: { "content-type": "application/json", ...(await clientHeaders()) },
    body: JSON.stringify({
      document_id: Number(form.get("document_id")),
      paragraph_index: paragraph === null || paragraph === "" ? null : Number(paragraph),
      message: message.slice(0, 2000),
    }),
  });
  if (res.status === 429) return { ok: false, message: "أرسلت بلاغات كثيرة. حاول مجدداً بعد قليل." };
  if (!res.ok) return { ok: false, message: "تعذّر إرسال البلاغ. حاول مجدداً بعد قليل." };
  return { ok: true, message: "وصل بلاغك إلى فريق التحرير. شكراً لك." };
}
