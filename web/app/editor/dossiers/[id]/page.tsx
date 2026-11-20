import { editorFetch } from "@/lib/editor";
import type { EditorDossier } from "@/lib/types";
import { DossierEditor } from "./DossierEditor";

export const dynamic = "force-dynamic";
export const metadata = { title: "تحرير ملف", robots: { index: false } };

export default async function DossierEdit({ params }: { params: Promise<{ id: string }> }) {
  const d = await editorFetch<EditorDossier>(`/api/editor/dossiers/${Number((await params).id)}`);
  return <DossierEditor initial={d} />;
}
