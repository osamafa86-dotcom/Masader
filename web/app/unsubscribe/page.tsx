import { UnsubscribeForm } from "@/components/NewsletterForms";

export const metadata = { title: "إلغاء الاشتراك", robots: { index: false } };

export default async function UnsubscribePage({ searchParams }: { searchParams: Promise<{ token?: string }> }) {
  const token = (await searchParams).token ?? "";
  return (
    <div className="prose">
      <h1 className="page-title">إلغاء الاشتراك</h1>
      {token ? <><p className="page-lede">اضغط الزر لإيقاف النشرة الأسبوعية.</p><UnsubscribeForm token={token} /></>
        : <p className="notice error">الرابط ناقص. افتح الرابط كما وصلك في النشرة.</p>}
    </div>
  );
}
