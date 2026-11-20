import { engine } from "@/lib/api";
import { editorFetch } from "@/lib/editor";
import { ImportForm } from "./ImportForm";

export const dynamic = "force-dynamic";
export const metadata = { title: "استيراد مادة", robots: { index: false } };

export default async function ImportPage() {
  // Any source can receive imports, including those without a feed (e.g. Studies in Intelligence).
  await editorFetch("/api/editor/me"); // redirects to the login page when the session has expired
  const all = (await engine<{ slug: string; name_ar: string }[]>("/api/sources")).data ?? [];
  return (
    <div className="prose">
      <h1 className="page-title">استيراد مادة</h1>
      <p className="page-lede">
        الصق رابط صفحة أو ملف PDF لمادة لا تصل عبر الرصد الآلي، مثل أعداد «دراسات في الاستخبارات».
        تمر المادة بخط المعالجة المعتاد، وتطبق عليها قواعد حقوق المصدر الذي تختاره.
      </p>
      <ImportForm sources={all} />
    </div>
  );
}
