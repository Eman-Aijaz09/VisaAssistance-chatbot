import type { RecommendationData, VisaDetail, VisaRecommendation } from "@/types";
import { RecommendationCard } from "./RecommendationCard";

interface Props {
  data: RecommendationData;
  activeCardId: string | null;
  cardDetails: Record<string, VisaDetail>;
  loadingCardDetail: boolean;
  onToggle: (item: VisaRecommendation) => void;
  onAsk: (item: VisaRecommendation) => void;
}

export function RecommendationList({
  data,
  activeCardId,
  cardDetails,
  loadingCardDetail,
  onToggle,
  onAsk,
}: Props) {
  return (
    <section className="lg:col-span-6 xl:col-span-5 h-full overflow-y-auto mist-backdrop p-4 sm:p-6 border-r border-border space-y-4">
      <div className="mb-1 flex items-start justify-between gap-3">
        <div>
          <h2 className="font-display text-xl font-bold text-foreground">Recommended routes</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            {data.relaxed && data.message ? data.message : "Matched to your parameters."}
          </p>
        </div>
        <span className="text-xs canopy-gradient text-primary-foreground font-semibold px-3 py-1.5 rounded-full shrink-0">
          {data.results.length} matches
        </span>
      </div>

      {data.results.length === 0 ? (
        <div className="surface-card rounded-2xl p-8 text-center">
          <div className="mx-auto w-11 h-11 rounded-full bg-muted flex items-center justify-center text-muted-foreground">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-4.35-4.35M11 19a8 8 0 100-16 8 8 0 000 16z" />
            </svg>
          </div>
          <p className="mt-3 font-display text-sm font-semibold text-foreground">
            No matching pathways yet
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            Try widening your budget, countries, or education options — or just ask the assistant.
          </p>
        </div>
      ) : (
        data.results.map((item) => (
          <RecommendationCard
            key={item.id}
            item={item}
            active={activeCardId === item.id}
            loadingDetail={activeCardId === item.id && loadingCardDetail}
            detail={cardDetails[item.id]}
            onToggle={onToggle}
            onAsk={onAsk}
          />
        ))
      )}
    </section>
  );
}
