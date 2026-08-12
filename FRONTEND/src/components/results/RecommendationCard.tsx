import type { VisaDetail, VisaRecommendation } from "@/types";
import { safeUrl } from "@/lib/sanitize";

interface Props {
  item: VisaRecommendation;
  active: boolean;
  loadingDetail: boolean;
  detail: VisaDetail | undefined;
  onToggle: (item: VisaRecommendation) => void;
  onAsk: (item: VisaRecommendation) => void;
}

export function RecommendationCard({ item, active, loadingDetail, detail, onToggle, onAsk }: Props) {
  const source = safeUrl(item.source_url);

  return (
    <div
      className={`bg-surface rounded-2xl overflow-hidden border transition-all duration-200 ${
        active
          ? "border-primary shadow-[var(--shadow-lift)]"
          : "border-border shadow-[var(--shadow-soft)] lift-on-hover"
      }`}
    >
      <button
        type="button"
        onClick={() => onToggle(item)}
        aria-expanded={active}
        className="w-full text-left p-5 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring/50 flex flex-col justify-between"
      >
        <div className="flex items-start justify-between w-full gap-3">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-[10px] font-bold uppercase tracking-[0.12em] text-secondary-foreground bg-secondary px-2 py-1 rounded-md">
              {item.country}
            </span>
            <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-primary bg-accent/25 px-2 py-1 rounded-md">
              {item.visa_type}
            </span>
          </div>
          <span
            className={`shrink-0 w-7 h-7 rounded-full flex items-center justify-center transition-all duration-200 ${
              active ? "bg-primary text-primary-foreground rotate-180" : "bg-muted text-muted-foreground"
            }`}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </span>
        </div>

        <h3 className="mt-3 font-display text-base font-bold text-foreground">{item.title}</h3>
        <p className={`mt-1 text-xs leading-relaxed text-muted-foreground ${active ? "" : "line-clamp-2"}`}>
          {item.summary}
        </p>

        <div className="mt-4 pt-3 border-t border-border flex items-center justify-between text-xs w-full">
          <span className="text-primary font-semibold">
            {active ? "Collapse details" : "View full policy details \u2192"}
          </span>
          {source && (
            <a
              href={source}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="text-muted-foreground hover:text-primary underline underline-offset-2 text-[11px]"
            >
              Official source
            </a>
          )}
        </div>
      </button>

      {active && (
        <div className="border-t border-border bg-surface-sunken p-5 space-y-4 text-xs text-foreground/80">
          {loadingDetail && (
            <div className="py-4 text-center text-muted-foreground flex items-center justify-center gap-2">
              <svg className="animate-spin w-4 h-4 text-primary" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              <span>Fetching full visa documentation…</span>
            </div>
          )}

          {!loadingDetail && detail && (
            <div className="space-y-4">
              {detail.eligibility?.length > 0 && (
                <Section title="Eligibility criteria">
                  <ul className="text-muted-foreground bg-surface p-3.5 rounded-xl border border-border space-y-1.5 list-disc list-inside">
                    {detail.eligibility.map((point, i) => (
                      <li key={i}>{point}</li>
                    ))}
                  </ul>
                </Section>
              )}

              {detail.required_documents?.length > 0 && (
                <Section title="Required documents">
                  <ul className="text-muted-foreground bg-surface p-3.5 rounded-xl border border-border space-y-1.5 list-disc list-inside">
                    {detail.required_documents.map((doc, i) => (
                      <li key={i}>{doc}</li>
                    ))}
                  </ul>
                </Section>
              )}

              {detail.application_process?.length > 0 && (
                <Section title="Application process">
                  <ol className="text-muted-foreground bg-surface p-3.5 rounded-xl border border-border space-y-1.5 list-decimal list-inside">
                    {detail.application_process.map((step, i) => (
                      <li key={i}>{step}</li>
                    ))}
                  </ol>
                </Section>
              )}

              {(detail.application_fee || detail.total_estimated_cost) && (
                <Section title="Fees & costs">
                  <dl className="grid grid-cols-2 gap-2">
                    {detail.application_fee && (
                      <Stat label="Application fee" value={detail.application_fee} />
                    )}
                    {detail.total_estimated_cost != null && (
                      <Stat
                        label="Estimated total"
                        value={`${detail.total_estimated_cost} ${detail.cost_currency ?? ""}`}
                      />
                    )}
                    {detail.processing_time && (
                      <Stat label="Processing time" value={detail.processing_time} />
                    )}
                    {detail.validity && <Stat label="Validity" value={detail.validity} />}
                  </dl>
                </Section>
              )}

              {detail.important_notes?.length > 0 && (
                <Section title="Important notes">
                  <ul className="text-muted-foreground bg-accent/15 p-3.5 rounded-xl border border-accent/40 space-y-1.5 list-disc list-inside">
                    {detail.important_notes.map((note, i) => (
                      <li key={i}>{note}</li>
                    ))}
                  </ul>
                </Section>
              )}

              {detail.last_verified_date && (
                <p className="text-[10px] text-muted-foreground italic">
                  Last verified: {detail.last_verified_date}
                </p>
              )}

              <button
                type="button"
                onClick={() => onAsk(item)}
                className="w-full py-2.5 canopy-gradient text-primary-foreground font-semibold rounded-xl text-xs flex items-center justify-center gap-2 transition hover:brightness-110 focus:outline-none focus-visible:ring-4 focus-visible:ring-ring/30"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                </svg>
                <span>Ask the assistant about this visa</span>
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h4 className="font-display font-semibold text-foreground text-xs mb-1.5">{title}</h4>
      {children}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-surface border border-border rounded-xl p-3">
      <dt className="text-[10px] uppercase tracking-[0.1em] text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 text-xs font-semibold text-foreground">{value}</dd>
    </div>
  );
}
