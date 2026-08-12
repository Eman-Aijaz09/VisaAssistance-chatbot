export type View = "form" | "results";

export interface VisaRecommendation {
  id: string;
  country: string;
  visa_type: string;
  title: string;
  summary: string;
  source_url: string | null;
}

export interface ActiveContext {
  country: string | null;
  visa_type: string | null;
  visa_id: string | null;   // NEW — matches VisaRecommendation.id (string)
}

export interface VisaDetail {
  eligibility: string[];
  required_documents: string[];
  application_process: string[];
  application_fee: string | null;
  total_estimated_cost: number | null;
  cost_currency: string | null;
  processing_time: string | null;
  validity: string | null;
  important_notes: string[];
  last_verified_date: string | null;
}

export interface Source {
  title: string;
  source_url: string;
  last_verified_date: string | null;
}

export interface ChatMessage {
  role: "user" | "assistant";
  text: string;
  sources?: Source[];
}

export interface RecommendationData {
  relaxed: boolean;
  message: string | null;
  results: VisaRecommendation[];
}

export interface FormData {
  purpose: string;
  countriesInput: string;
  education_level: string;
  // language_test: string;
  // language_score: string;
  budget: number | null;
  budget_currency: string;
}

export interface AskResponse {
  answer: string;
  sources: Source[];
  updated_recommendations?: VisaRecommendation[];
}
