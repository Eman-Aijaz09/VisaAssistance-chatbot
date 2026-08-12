import type { FormData } from "@/types";

const inputClass =
  "w-full rounded-xl border border-input bg-surface py-3 px-4 text-foreground text-sm placeholder:text-muted-foreground/70 transition focus:border-ring focus:outline-none focus:ring-4 focus:ring-ring/15";
const labelClass =
  "block text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground mb-2";

interface Props {
  formData: FormData;
  loading: boolean;
  error: string | null;
  onChange: (patch: Partial<FormData>) => void;
  onSubmit: () => void;
}

const highlights = [
  { label: "Official sources", detail: "Every answer is cited" },
  { label: "Budget aware", detail: "Fees in your currency" },
  { label: "Live guidance", detail: "Ask follow-up questions" },
];

export function RecommendationForm({ formData, loading, error, onChange, onSubmit }: Props) {
  return (
    <main className="flex-1 overflow-y-auto mist-backdrop w-full">
      <div className="mx-auto w-full max-w-3xl px-4 py-10 sm:px-6 sm:py-14 lg:px-8">
        <div className="text-center mb-9">
          <span className="inline-flex items-center gap-2 rounded-full border border-border bg-surface/70 px-3.5 py-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-primary">
            <span className="w-1.5 h-1.5 rounded-full bg-accent" />
            Guided visa matching
          </span>
          <h1 className="mt-5 font-display text-4xl font-bold text-foreground sm:text-5xl text-balance">
            Find your ideal destination
          </h1>
          <p className="mt-3 text-muted-foreground text-sm sm:text-base max-w-xl mx-auto">
            Tell us where you stand today. We match immigration pathways to your goals and answer
            policy questions with cited official sources.
          </p>
        </div>

        <div className="surface-card rounded-3xl p-6 sm:p-8">
          <form
            className="space-y-7"
            onSubmit={(e) => {
              e.preventDefault();
              onSubmit();
            }}
          >
            <fieldset className="space-y-5">
              <legend className="font-display text-sm font-semibold text-foreground mb-1">
                1 &middot; Your goal
              </legend>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                <div>
                  <label className={labelClass} htmlFor="purpose">
                    Primary goal
                  </label>
                  <select
                    id="purpose"
                    className={inputClass}
                    value={formData.purpose}
                    onChange={(e) => onChange({ purpose: e.target.value })}
                  >
                    <option value="">Any purpose</option>
                    <option value="Work">Work / Employment</option>
                    <option value="Study">Higher education / Study</option>
                    <option value="Permanent Residency">Permanent residency</option>
                    <option value="Business">Business / Investment</option>
                  </select>
                </div>

                <div>
                  <label className={labelClass} htmlFor="countries">
                    Target countries
                  </label>
                  <input
                    id="countries"
                    type="text"
                    className={inputClass}
                    placeholder="Canada, Germany, Australia"
                    value={formData.countriesInput}
                    onChange={(e) => onChange({ countriesInput: e.target.value })}
                  />
                  <p className="mt-1.5 text-[11px] text-muted-foreground">
                    Separate multiple countries with commas.
                  </p>
                </div>
              </div>
            </fieldset>

            <div className="h-px bg-border" />

            <fieldset className="space-y-5">
              <legend className="font-display text-sm font-semibold text-foreground mb-1">
                2 &middot; Your profile
              </legend>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                <div>
                  <label className={labelClass} htmlFor="education">
                    Education level
                  </label>
                  <select
                    id="education"
                    className={inputClass}
                    value={formData.education_level}
                    onChange={(e) => onChange({ education_level: e.target.value })}
                  >
                    <option value="">Select education</option>
                    <option value="master">Master&apos;s degree or doctorate</option>
                    <option value="bachelor's">Bachelor&apos;s degree</option>
                    <option value="diploma">Associate degree / Diploma</option>
                    <option value="high School">High school diploma</option>
                  </select>
                </div>

                <div>
                  <label className={labelClass} htmlFor="budget">
                    Available budget (PKR)
                  </label>
                  <div className="relative">
                    <span className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-4 text-muted-foreground font-medium text-sm">
                      Rs
                    </span>
                    <input
                      id="budget"
                      type="number"
                      min={0}
                      className="w-full rounded-xl border border-input bg-surface py-3 pl-10 pr-4 text-foreground text-sm placeholder:text-muted-foreground/70 transition focus:border-ring focus:outline-none focus:ring-4 focus:ring-ring/15"
                      placeholder="25000"
                      value={formData.budget ?? ""}
                      onChange={(e) =>
                        onChange({ budget: e.target.value === "" ? null : Number(e.target.value) })
                      }
                    />
                  </div>
                </div>

                {/* <div>
                  <label className={labelClass} htmlFor="language_test">
                    Language test
                  </label>
                  <input
                    id="language_test"
                    type="text"
                    className={inputClass}
                    placeholder="IELTS, TOEFL, TEF"
                    value={formData.language_test}
                    onChange={(e) => onChange({ language_test: e.target.value })}
                  />
                </div>

                <div>
                  <label className={labelClass} htmlFor="language_score">
                    Language score
                  </label>
                  <input
                    id="language_score"
                    type="text"
                    className={inputClass}
                    placeholder="8.0 or CLB 9"
                    value={formData.language_score}
                    onChange={(e) => onChange({ language_score: e.target.value })}
                  />
                </div> */}
              </div>
            </fieldset>

            {error && (
              <div
                role="alert"
                className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
              >
                {error}
              </div>
            )}

            <div className="pt-1">
              <button
                type="submit"
                disabled={loading}
                className="w-full canopy-gradient text-primary-foreground font-semibold py-4 px-6 rounded-2xl shadow-[var(--shadow-soft)] transition-all hover:brightness-110 disabled:opacity-60 flex items-center justify-center gap-2 text-base focus:outline-none focus-visible:ring-4 focus-visible:ring-ring/30"
              >
                {loading ? (
                  <>
                    <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    <span>Analyzing your options…</span>
                  </>
                ) : (
                  <>
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                    <span>Analyze my eligibility</span>
                  </>
                )}
              </button>
              <p className="mt-3 text-center text-[11px] text-muted-foreground">
                Guidance only — always confirm details with the official immigration authority.
              </p>
            </div>
          </form>
        </div>

        <ul className="mt-8 grid grid-cols-1 sm:grid-cols-3 gap-3">
          {highlights.map((h) => (
            <li
              key={h.label}
              className="rounded-2xl border border-border bg-surface/60 px-4 py-3.5 text-center sm:text-left"
            >
              <p className="text-sm font-semibold text-foreground">{h.label}</p>
              <p className="text-xs text-muted-foreground mt-0.5">{h.detail}</p>
            </li>
          ))}
        </ul>
      </div>
    </main>
  );
}
