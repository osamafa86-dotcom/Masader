import { ConfirmForm } from "@/components/NewsletterForms";

export const metadata = { title: "تأكيد الاشتراك", robots: { index: false } };

export default async function ConfirmPage({ searchParams }: { searchParams: Promise<{ token?: string }> }) {
  const token = (await searchParams).token ?? "";
  return (
    <div className="prose">
      <h1 className="page-title">تأكيد الاشتراك</h1>
      {token ? <><p className="page-lede">اضغط الزر لتأكيد اشتراكك في النشرة الأسبوعية.</p><ConfirmForm token={token} /></>
        : <p className="notice error">الرابط ناقص. افتح الرابط كما وصلك في رسالة التأكيد.</p>}
    </div>
  );
}
