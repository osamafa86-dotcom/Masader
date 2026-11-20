import Link from "next/link";

export default function NotFound() {
  return (
    <div className="prose">
      <h1 className="page-title">الصفحة غير موجودة</h1>
      <p className="page-lede">ربما أُزيلت المادة أو تغيّر رابطها. ابحث عنها من مربع البحث، أو عُد إلى <Link href="/">آخر ما رُصد</Link>.</p>
    </div>
  );
}
