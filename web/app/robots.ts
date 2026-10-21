import type { MetadataRoute } from "next";

const SITE = "https://www.holasabi.com";

// Public pages are open to every crawler, including AI/LLM agents. Only the private owner panel,
// login and API stay out of indexes (they are behind a login or are not pages).
const PRIVATE = ["/api/", "/login", "/pedidos", "/menu", "/config", "/registro", "/eventos/admin"];

const AI_CRAWLERS = [
  "GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-User", "Claude-SearchBot",
  "anthropic-ai", "PerplexityBot", "Perplexity-User", "Google-Extended", "Applebot-Extended",
  "CCBot", "Bytespider", "cohere-ai", "Meta-ExternalAgent", "Amazonbot", "DuckAssistBot",
];

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      { userAgent: "*", allow: "/", disallow: PRIVATE },
      { userAgent: AI_CRAWLERS, allow: "/", disallow: PRIVATE },
    ],
    sitemap: `${SITE}/sitemap.xml`,
    host: SITE,
  };
}
