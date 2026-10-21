import type { MetadataRoute } from "next";

const SITE = "https://www.holasabi.com";

export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();
  return [
    { url: `${SITE}/`, lastModified: now, changeFrequency: "weekly", priority: 1 },
    { url: `${SITE}/eventos`, lastModified: now, changeFrequency: "weekly", priority: 0.8 },
    { url: `${SITE}/llms.txt`, lastModified: now, changeFrequency: "monthly", priority: 0.3 },
  ];
}
