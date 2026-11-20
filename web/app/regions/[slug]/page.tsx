import { TaxonomyListing } from "@/components/Listing";

export const revalidate = 60;

export default async function RegionPage({ params, searchParams }: { params: Promise<{ slug: string }>; searchParams: Promise<{ page?: string }> }) {
  const [{ slug }, sp] = await Promise.all([params, searchParams]);
  return <TaxonomyListing kind="region" slug={slug} page={Number(sp.page ?? 1) || 1} />;
}
