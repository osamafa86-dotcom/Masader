import Link from "next/link";
import { engine } from "@/lib/api";
import { newsletterChoices } from "@/lib/choices";
import { ManageForm } from "@/components/NewsletterForms";
import type { Subscription } from "@/lib/types";

export const dynamic = "force-dynamic";
export const metadata = { title: "إعدادات النشرة", robots: { index: false } };

export default async function ManagePage({ searchParams }: { searchParams: Promise<{ token?: string }> }) {
  const token = (await searchParams).token ?? "";
  const { status, data } = token ? await engine<Subscription>(`/api/subscription/${encodeURIComponent(token)}`) : { status: 404, data: null };
  if (status !== 200 || !data) {
    return <div className="prose"><h1 className="page-title">إعدادات النشرة</h1><p className="notice error">الرابط غير صالح أو منتهٍ. <Link href="/subscribe">اشترك من جديد</Link>.</p></div>;
  }
  const choices = await newsletterChoices();
  return (
    <div className="prose">
      <h1 className="page-title">إعدادات النشرة</h1>
      <p className="page-lede">
        الاشتراك باسم <bdi dir="ltr">{data.email}</bdi>{data.active ? "، وهو فعّال." : "، وهو غير فعّال حالياً."}
      </p>
      <ManageForm token={token} sub={data} choices={choices} />
      <p className="ui" style={{ marginTop: "2rem" }}><Link href={`/unsubscribe?token=${encodeURIComponent(token)}`}>إلغاء الاشتراك</Link></p>
    </div>
  );
}
