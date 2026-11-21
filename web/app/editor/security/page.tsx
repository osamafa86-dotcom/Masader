import { editorFetch } from "@/lib/editor";
import { TwoFactor } from "./TwoFactor";

export const dynamic = "force-dynamic";
export const metadata = { title: "الأمان", robots: { index: false } };

export default async function Security({ searchParams }: { searchParams: Promise<{ required?: string }> }) {
  const me = await editorFetch<{ email: string; totp_enabled: boolean; two_factor_required: boolean }>("/api/editor/me");
  const required = (await searchParams).required;
  return (
    <div className="prose">
      <h1 className="page-title">الأمان</h1>
      {required && !me.totp_enabled && <p className="notice error">تشترط إدارة الموقع التحقق بخطوتين لكل المحررين. فعّله للمتابعة.</p>}
      <p className="page-lede">
        التحقق بخطوتين يطلب رمزاً من تطبيق مصادقة على هاتفك (مثل Google Authenticator أو 1Password) عند كل دخول،
        فلا تكفي كلمة المرور وحدها لدخول حسابك.
      </p>
      <TwoFactor enabled={me.totp_enabled} />
    </div>
  );
}
