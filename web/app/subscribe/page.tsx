import { SubscribeForm } from "@/components/NewsletterForms";
import { newsletterChoices } from "@/lib/choices";

export const dynamic = "force-dynamic";
export const metadata = { title: "النشرة الأسبوعية" };

export default async function SubscribePage() {
  const choices = await newsletterChoices();
  return (
    <div className="prose">
      <h1 className="page-title">النشرة الأسبوعية</h1>
      <p className="page-lede">
        مختارات أسبوعية من أهم ما رصدناه، يراجعها المحررون قبل الإرسال. يمكنك أن تحصرها في موضوعات أو مصادر
        أو كلمات بعينها، فلا تصلك رسالة في أسبوع لا جديد فيه يطابق اختيارك.
      </p>
      <SubscribeForm choices={choices} />
    </div>
  );
}
