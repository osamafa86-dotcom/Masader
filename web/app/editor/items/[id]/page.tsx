import { notFound } from "next/navigation";
import { editorFetch } from "@/lib/editor";
import type { EditorItem } from "@/lib/types";
import { ItemEditor } from "./ItemEditor";

export const dynamic = "force-dynamic";
export const metadata = { title: "مراجعة مادة", robots: { index: false } };

export default async function ItemPage({ params }: { params: Promise<{ id: string }> }) {
  const id = Number((await params).id);
  if (!Number.isInteger(id)) notFound();
  const item = await editorFetch<EditorItem>(`/api/editor/items/${id}`).catch((e: Error) => {
    if (e.message.includes("غير موجودة")) notFound();
    throw e;
  });
  return <ItemEditor initial={item} />;
}
