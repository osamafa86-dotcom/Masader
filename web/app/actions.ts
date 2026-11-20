"use server";
import { ENGINE_URL } from "@/lib/api";

export type FeedbackState = { ok: boolean; message: string } | null;

export async function sendFeedback(_prev: FeedbackState, form: FormData): Promise<FeedbackState> {
  const message = String(form.get("message") ?? "").trim();
  if (message.length < 3) return { ok: false, message: "اكتب وصفاً قصيراً للخطأ قبل الإرسال." };
  const paragraph = form.get("paragraph_index");
  const res = await fetch(`${ENGINE_URL}/api/feedback`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      document_id: Number(form.get("document_id")),
      paragraph_index: paragraph === null || paragraph === "" ? null : Number(paragraph),
      message: message.slice(0, 2000),
    }),
  });
  if (!res.ok) return { ok: false, message: "تعذّر إرسال البلاغ. حاول مجدداً بعد قليل." };
  return { ok: true, message: "وصل بلاغك إلى فريق التحرير. شكراً لك." };
}
