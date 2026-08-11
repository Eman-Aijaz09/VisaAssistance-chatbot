import { useCallback, useState } from "react";
import { Header } from "@/components/layout/Header";
import { Sidebar } from "@/components/layout/Sidebar";
import { RecommendationForm } from "@/components/form/RecommendationForm";
import { RecommendationList } from "@/components/results/RecommendationList";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { getVisaDetail, postAsk, postRecommend } from "@/lib/api";
import type {
  ChatMessage,
  FormData,
  RecommendationData,
  View,
  VisaDetail,
  VisaRecommendation,
} from "@/types";

// Session id lives in memory only for the life of the tab.
// Never persist chat content or personal form data (education, budget, ...).
function newSessionId() {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2);
}

export function ImmigrationAssistantApp() {
  const [sessionId] = useState<string>(() => newSessionId());
  const [view, setView] = useState<View>("form");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const [loadingForm, setLoadingForm] = useState(false);
  const [loadingChat, setLoadingChat] = useState(false);
  const [loadingCardDetail, setLoadingCardDetail] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [formData, setFormData] = useState<FormData>({
    purpose: "Work",
    countriesInput: "Canada, Germany",
    education_level: "master",
    language_test: "IELTS",
    language_score: "8.0",
    budget: 25000,
    budget_currency: "PKR",
  });

  const [recommendationData, setRecommendationData] = useState<RecommendationData>({
    relaxed: false,
    message: null,
    results: [],
  });

  const [activeCardId, setActiveCardId] = useState<string | null>(null);
  const [cardDetails, setCardDetails] = useState<Record<string, VisaDetail>>({});
  const [activeContext, setActiveContext] = useState<{
    country: string | null;
    visa_type: string | null;
  }>({ country: null, visa_type: null });

  const [chatInput, setChatInput] = useState("");
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);

  const resetToForm = useCallback(() => {
    setView("form");
    setActiveCardId(null);
    setActiveContext({ country: null, visa_type: null });
  }, []);

  const submitForm = async () => {
    // UX-level validation only — the backend must validate again.
    if (formData.budget != null && (Number.isNaN(formData.budget) || formData.budget < 0)) {
      setFormError("Budget must be a non-negative number.");
      return;
    }
    setFormError(null);
    setLoadingForm(true);

    const countriesArr = formData.countriesInput
      ? formData.countriesInput
          .split(",")
          .map((c) => c.trim())
          .filter(Boolean)
      : null;

    try {
      const data = await postRecommend({
        session_id: sessionId,
        countries: countriesArr && countriesArr.length > 0 ? countriesArr : null,
        purpose: formData.purpose || null,
        education_level: formData.education_level || null,
        language_test: formData.language_test || null,
        language_score: formData.language_score || null,
        budget: formData.budget ?? null,
        budget_currency: formData.budget_currency || null,
      });

      setRecommendationData(data);
      setCardDetails({});
      setActiveCardId(null);
      setChatMessages([
        {
          role: "assistant",
          text: `I've evaluated your parameters and retrieved ${data.results?.length ?? 0} matching pathways. Feel free to expand any route on the left or ask me questions directly!`,
          sources: [],
        },
      ]);
      setView("results");
    } catch (err) {
      setFormError(
        `Failed to fetch recommendations: ${err instanceof Error ? err.message : "Unknown error"}`,
      );
    } finally {
      setLoadingForm(false);
    }
  };

  const toggleCard = async (item: VisaRecommendation) => {
    if (activeCardId === item.id) {
      setActiveCardId(null);
      setActiveContext({ country: null, visa_type: null });
      return;
    }

    setActiveCardId(item.id);
    setActiveContext({ country: item.country, visa_type: item.visa_type });

    if (!cardDetails[item.id]) {
      setLoadingCardDetail(true);
      try {
        const detail = await getVisaDetail(item.id);
        setCardDetails((prev) => ({ ...prev, [item.id]: detail }));
      } catch (err) {
        console.error("Failed to fetch visa details:", err);
      } finally {
        setLoadingCardDetail(false);
      }
    }
  };

  const sendChat = async (rawQuery: string) => {
    const query = rawQuery.trim();
    if (!query || loadingChat) return;

    setChatMessages((prev) => [...prev, { role: "user", text: query }]);
    setChatInput("");
    setLoadingChat(true);

    try {
      const data = await postAsk({
        session_id: sessionId,
        query,
        context_country: activeContext.country,
        context_visa_type: activeContext.visa_type,
      });

      setChatMessages((prev) => [
        ...prev,
        { role: "assistant", text: data.answer, sources: data.sources ?? [] },
      ]);

      if (data.updated_recommendations) {
        setRecommendationData((prev) => ({
          ...prev,
          results: data.updated_recommendations!,
        }));
        setActiveCardId(null);
        setCardDetails({});
      }
    } catch (err) {
      setChatMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: `Sorry, I encountered an error answering your question: ${
            err instanceof Error ? err.message : "Unknown error"
          }`,
          sources: [],
        },
      ]);
    } finally {
      setLoadingChat(false);
    }
  };

  return (
    <div className="bg-background text-foreground antialiased h-screen flex flex-col overflow-hidden">
      <Header
        showEdit={view === "results"}
        onOpenSidebar={() => setSidebarOpen(true)}
        onReset={resetToForm}
      />

      <div className="flex flex-1 relative overflow-hidden">
        <Sidebar
          open={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
          onNewAssessment={() => {
            resetToForm();
            setSidebarOpen(false);
          }}
        />

        {view === "form" ? (
          <RecommendationForm
            formData={formData}
            loading={loadingForm}
            error={formError}
            onChange={(patch) => setFormData((prev) => ({ ...prev, ...patch }))}
            onSubmit={submitForm}
          />
        ) : (
          <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 h-full overflow-hidden w-full">
            <RecommendationList
              data={recommendationData}
              activeCardId={activeCardId}
              cardDetails={cardDetails}
              loadingCardDetail={loadingCardDetail}
              onToggle={toggleCard}
              onAsk={(item) =>
                sendChat(
                  `What are the step-by-step application requirements for the ${item.title} in ${item.country}?`,
                )
              }
            />
            <ChatPanel
              messages={chatMessages}
              loading={loadingChat}
              input={chatInput}
              contextCountry={activeContext.country}
              contextVisaType={activeContext.visa_type}
              onInputChange={setChatInput}
              onSend={() => sendChat(chatInput)}
            />
          </div>
        )}
      </div>
    </div>
  );
}
