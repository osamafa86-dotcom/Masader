import "server-only";
import { api } from "./api";

export async function newsletterChoices() {
  const [topics, sources] = await Promise.all([api.topics(), api.sources()]);
  return {
    topics: topics.topic,
    regions: topics.region,
    sources: sources.filter((s) => s.is_active).map((s) => ({ slug: s.slug, name_ar: s.name_ar })),
  };
}
