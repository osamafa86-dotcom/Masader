import { LoginForm } from "./LoginForm";

export const metadata = { title: "دخول المحررين", robots: { index: false } };

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ expired?: string }> }) {
  const expired = (await searchParams).expired;
  return (
    <div style={{ maxWidth: 420, margin: "2rem auto" }}>
      <h1 className="page-title">دخول المحررين</h1>
      {expired && <p className="notice">انتهت جلستك. سجّل الدخول مجدداً للمتابعة.</p>}
      <LoginForm />
    </div>
  );
}
