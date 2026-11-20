import { SITE_URL } from "@/lib/format";

export const metadata = { title: "الواجهة البرمجية للمؤسسات" };

const ENDPOINTS: [string, string][] = [
  ["GET /v1/articles", "المواد المنشورة، مع ترشيح بالموضوع والمنطقة والمصدر واللغة الأصلية والتاريخ"],
  ["GET /v1/articles/{id}", "مادة واحدة بملخصها، ونصها المترجم كاملاً حيث تسمح الحقوق"],
  ["GET /v1/search?q=&mode=", "بحث بالكلمات أو بالمعنى، بالعربية أو بلغة الأصل"],
  ["GET /v1/sources", "المصادر المرصودة ومستوى حقوق كل منها"],
  ["GET /v1/topics", "التصنيف الموضوعي والجغرافي مع الأعداد"],
  ["GET /v1/dossiers", "الملفات الموضوعية المنشورة"],
  ["GET /v1/trends/{YYYY-MM}", "إحصاءات الشهر والقراءة المنشورة"],
  ["GET /v1/glossary", "المسرد المعتمد للمصطلحات"],
];

export default function Developers() {
  const base = SITE_URL.replace(/\/$/, "");
  return (
    <div className="prose" style={{ maxWidth: 860 }}>
      <h1 className="page-title">الواجهة البرمجية للمؤسسات</h1>
      <p className="page-lede">
        تتيح الواجهة لمراكز الأبحاث والجامعات والمؤسسات الإعلامية دمج ملخصات المرصد وترجماته في أنظمتها، بصيغة JSON ثابتة ومعرّفة.
      </p>
      <h2>الحصول على مفتاح</h2>
      <p>تصدر المفاتيح يدوياً للمؤسسات. راسل فريق التحرير باسم المؤسسة والغرض من الاستخدام وعدد الطلبات المتوقع.
        يظهر المفتاح مرة واحدة عند إصداره، فاحفظه في مكان آمن.</p>
      <h2>الاستخدام</h2>
      <p>أرسل المفتاح في الترويسة <bdi dir="ltr" className="latin">X-API-Key</bdi>. لكل مفتاح حد للطلبات في الدقيقة، وتبيّن ترويسات
        <bdi dir="ltr" className="latin"> X-RateLimit-* </bdi>المتبقي منه. عند تجاوزه تعود الاستجابة بالرمز 429 مع مدة الانتظار.</p>
      <pre className="cite" dir="ltr" lang="en">{`curl -H "X-API-Key: mrsd_..." "${base}/v1/articles?topic=deterrence&per_page=20"`}</pre>
      <table className="glossary-table" style={{ margin: "1.5rem 0" }}>
        <thead><tr><th scope="col">الطلب</th><th scope="col">ما يعيده</th></tr></thead>
        <tbody>{ENDPOINTS.map(([path, desc]) => <tr key={path}><td className="en" dir="ltr">{path}</td><td>{desc}</td></tr>)}</tbody>
      </table>
      <p><a href={`${base}/v1/docs`}>التوثيق التفاعلي الكامل (بالإنجليزية)</a></p>
      <h2>الحقوق</h2>
      <p>تطبق الواجهة قواعد الموقع نفسها: لا يُعاد النص الكامل إلا حين يسمح ترخيص المصدر أو إذنه بذلك. احتفظ عند العرض باسم المصدر
        والمؤلفين ورابط الأصل والترخيص، واذكر المرصد مصدراً للترجمة والملخص.</p>
    </div>
  );
}
