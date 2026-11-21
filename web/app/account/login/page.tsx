import { LoginForm } from "@/components/AccountForms";
import { SITE_NAME } from "@/lib/format";

export const metadata = { title: "الدخول إلى حسابك", robots: { index: false } };

export default function AccountLogin() {
  return (
    <div className="prose" style={{ maxWidth: 520 }}>
      <h1 className="page-title">حسابك في {SITE_NAME}</h1>
      <p className="page-lede">احفظ المواد في مكتبة خاصة بك مع ملاحظاتك، واختر تنبيهاتك. لا كلمة مرور: نرسل إليك رابط دخول صالحاً لمرة واحدة.</p>
      <LoginForm />
    </div>
  );
}
