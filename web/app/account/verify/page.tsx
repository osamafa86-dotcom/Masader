import { VerifyForm } from "@/components/AccountForms";

export const metadata = { title: "الدخول", robots: { index: false } };

export default async function Verify({ searchParams }: { searchParams: Promise<{ token?: string }> }) {
  const token = (await searchParams).token ?? "";
  return (
    <div className="prose" style={{ maxWidth: 520 }}>
      <h1 className="page-title">الدخول إلى حسابك</h1>
      {token ? <VerifyForm token={token} /> : <p className="notice error">الرابط ناقص. افتحه كما وصلك في البريد.</p>}
    </div>
  );
}
