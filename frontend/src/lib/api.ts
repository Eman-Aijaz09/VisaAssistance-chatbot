import type {
  AskResponse,
  RecommendationData,
  VisaDetail,
} from "@/types";

/**
 * Public config only — never put API keys or tokens in client code.
 * Defaults to a local dev origin; production must supply an https:// origin.
 *
 * Backend/CORS note: the API should restrict Access-Control-Allow-Origin to the
 * deployed frontend's actual domain (not "*"), since this app sends session ids.
 */
export const API_BASE_URL: string =
  (import.meta.env["VITE_API_BASE_URL"] as string | undefined) ??
  "http://127.0.0.1:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    credentials: "omit",
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) throw new Error(res.statusText || `Request failed (${res.status})`);
  return (await res.json()) as T;
}

export interface RecommendPayload {
  session_id: string;
  countries: string[] | null;
  purpose: string | null;
  education_level: string | null;
  language_test: string | null;
  language_score: string | null;
  budget: number | null;
  budget_currency: string | null;
}

export function postRecommend(payload: RecommendPayload) {
  return request<RecommendationData>("/recommend", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getVisaDetail(id: string) {
  return request<VisaDetail>(`/visa-detail/${encodeURIComponent(id)}`);
}

export interface AskPayload {
  session_id: string;
  query: string;
  context_country: string | null;
  context_visa_type: string | null;
   context_visa_id: string | null;   // NEW
}

export function postAsk(payload: AskPayload) {
  return request<AskResponse>("/ask", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
