import { createFileRoute } from "@tanstack/react-router";
import { ImmigrationAssistantApp } from "@/components/ImmigrationAssistantApp";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Immigration Assistant — Find Your Visa Pathway" },
      {
        name: "description",
        content:
          "Compare immigration pathways by country, budget and education, then ask an AI assistant policy questions with cited official sources.",
      },
      { property: "og:title", content: "Immigration Assistant — Find Your Visa Pathway" },
      {
        property: "og:description",
        content:
          "AI-matched visa routes with eligibility, documents, fees and a cited policy chat assistant.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: ImmigrationAssistantApp,
});
