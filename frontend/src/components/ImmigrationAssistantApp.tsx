import { useCallback, useEffect, useState } from "react";
import { Header } from "@/components/layout/Header";
import { Sidebar } from "@/components/layout/Sidebar";
import { RecommendationForm } from "@/components/form/RecommendationForm";
import { RecommendationList } from "@/components/results/RecommendationList";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { getVisaDetail, postAsk, postRecommend } from "@/lib/api";
import type {
  FormData,
  RecommendationData,
  Session,
  VisaDetail,
  VisaRecommendation,
} from "@/types";

// Sessions are persisted to sessionStorage so a page refresh doesn't lose
// conversation history. sessionStorage clears when the tab closes, but is
// still readable by any script on this origin while the tab is open —
// acceptable for now since there's no auth or highly sensitive data.
const SESSION_STORAGE_KEY = "immigration-assistant:sessions";
const ACTIVE_ID_STORAGE_KEY = "immigration-assistant:active-session-id";

function newSessionId() {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2);
}

const defaultFormData: FormData = {
  purpose: "Work",
  countries: ["Germany"],
  education_level: "master",
  budget: 25000,
  budget_currency: "PKR",
};

function makeEmptySession(): Session {
  return {
    id: newSessionId(),
    label: "New assessment",
    createdAt: Date.now(),
    view: "form",
    formData: defaultFormData,
    recommendationData: { relaxed: false, message: null, results: [] },
    activeCardId: null,
    cardDetails: {},
    activeContext: { country: null, visa_type: null, visa_id: null },
    chatMessages: [],
  };
}

function loadPersistedSessions(): Session[] | null {
  try {
    const raw = sessionStorage.getItem(SESSION_STORAGE_KEY);
    if (raw) {
      const parsed: Session[] = JSON.parse(raw);
      if (Array.isArray(parsed) && parsed.length > 0) return parsed;
    }
  } catch {
    // corrupt or unavailable storage — ignore, start fresh
  }
  return null;
}

function loadPersistedActiveId(): string | null {
  try {
    return sessionStorage.getItem(ACTIVE_ID_STORAGE_KEY);
  } catch {
    return null;
  }
}

function savePersistedSessions(sessions: Session[]) {
  try {
    sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(sessions));
  } catch {
    // storage full/unavailable — non-fatal
  }
}

function savePersistedActiveId(id: string) {
  try {
    sessionStorage.setItem(ACTIVE_ID_STORAGE_KEY, id);
  } catch {
    // non-fatal
  }
}

export function ImmigrationAssistantApp() {
  const [sessions, setSessions] = useState<Session[]>(() => loadPersistedSessions() ?? [makeEmptySession()]);
  const [activeSessionId, setActiveSessionId] = useState<string>(() => {
    const savedId = loadPersistedActiveId();
    const restored = loadPersistedSessions();
    if (savedId && restored?.some((s) => s.id === savedId)) return savedId;
    return restored?.[0]?.id ?? sessions[0]?.id ?? newSessionId();
  });

  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [loadingForm, setLoadingForm] = useState(false);
  const [loadingChat, setLoadingChat] = useState(false);
  const [loadingCardDetail, setLoadingCardDetail] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [chatInput, setChatInput] = useState("");

  const activeSession = sessions.find((s) => s.id === activeSessionId) ?? sessions[0] ?? makeEmptySession();

  useEffect(() => {
    savePersistedSessions(sessions);
  }, [sessions]);

  useEffect(() => {
    savePersistedActiveId(activeSessionId);
  }, [activeSessionId]);

  const updateActiveSession = useCallback(
    (patch: Partial<Session>) => {
      setSessions((prev) => prev.map((s) => (s.id === activeSessionId ? { ...s, ...patch } : s)));
    },
    [activeSessionId],
  );

  const resetToForm = useCallback(() => {
    updateActiveSession({
      view: "form",
      activeCardId: null,
      activeContext: { country: null, visa_type: null, visa_id: null },
    });
  }, [updateActiveSession]);

  const newChat = useCallback(() => {
    const fresh = makeEmptySession();
    setSessions((prev) => [fresh, ...prev]);
    setActiveSessionId(fresh.id);
    setSidebarOpen(false);
  }, []);

  const switchSession = useCallback((id: string) => {
    setActiveSessionId(id);
    setSidebarOpen(false);
  }, []);

  const deleteSession = useCallback(
    (id: string) => {
      setSessions((prev) => {
        const remaining = prev.filter((s) => s.id !== id);

        if (id === activeSessionId) {
          if (remaining.length > 0) {
            const sorted = [...remaining].sort((a, b) => b.createdAt - a.createdAt);
            const next = sorted[0];
            if (next) {
              setActiveSessionId(next.id);
            }
            return remaining;
          }
          const fresh = makeEmptySession();
          setActiveSessionId(fresh.id);
          return [fresh];
        }

        return remaining;
      });
    },
    [activeSessionId],
  );

  const submitForm = async () => {
    const { formData } = activeSession;

    // UX-level validation only — the backend must validate again.
    if (formData.budget != null && (Number.isNaN(formData.budget) || formData.budget < 0)) {
      setFormError("Budget must be a non-negative number.");
      return;
    }
    setFormError(null);
    setLoadingForm(true);

    try {
      const data = await postRecommend({
        session_id: activeSession.id,
        countries: formData.countries.length > 0 ? formData.countries : null,
        purpose: formData.purpose || null,
        education_level: formData.education_level || null,
        language_test: null,
        language_score: null,
        budget: formData.budget ?? null,
        budget_currency: formData.budget_currency || null,
      });

      const autoLabel =
        formData.purpose && formData.countries[0]
          ? `${formData.purpose} · ${formData.countries[0]}`
          : formData.countries[0] || formData.purpose || "New assessment";

      updateActiveSession({
        recommendationData: data,
        cardDetails: {},
        activeCardId: null,
        activeContext: { country: null, visa_type: null, visa_id: null },
        chatMessages: [
          {
            role: "assistant",
            text: `I've evaluated your parameters and retrieved ${data.results?.length ?? 0} matching pathways. Feel free to expand any route on the left or ask me questions directly!`,
            sources: [],
          },
        ],
        view: "results",
        label: autoLabel,
      });
    } catch (err) {
      setFormError(
        `Failed to fetch recommendations: ${err instanceof Error ? err.message : "Unknown error"}`,
      );
    } finally {
      setLoadingForm(false);
    }
  };

  const toggleCard = async (item: VisaRecommendation) => {
    const session = activeSession;

    if (session.activeCardId === item.id) {
      updateActiveSession({
        activeCardId: null,
        activeContext: { country: null, visa_type: null, visa_id: null },
      });
      return;
    }

    updateActiveSession({
      activeCardId: item.id,
      activeContext: { country: item.country, visa_type: item.visa_type, visa_id: item.id },
    });

    if (!session.cardDetails[item.id]) {
      setLoadingCardDetail(true);
      try {
        const detail = await getVisaDetail(item.id);
        setSessions((prev) =>
          prev.map((s) =>
            s.id === session.id ? { ...s, cardDetails: { ...s.cardDetails, [item.id]: detail } } : s,
          ),
        );
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

    const session = activeSession;

    setSessions((prev) =>
      prev.map((s) =>
        s.id === session.id ? { ...s, chatMessages: [...s.chatMessages, { role: "user", text: query }] } : s,
      ),
    );
    setChatInput("");
    setLoadingChat(true);

    try {
      const data = await postAsk({
        session_id: session.id,
        query,
        context_country: session.activeContext.country,
        context_visa_type: session.activeContext.visa_type,
        context_visa_id: session.activeContext.visa_id,
      });

      setSessions((prev) =>
        prev.map((s) => {
          if (s.id !== session.id) return s;
          const updated: Session = {
            ...s,
            chatMessages: [
              ...s.chatMessages,
              { role: "assistant", text: data.answer, sources: data.sources ?? [] },
            ],
          };
          if (data.updated_recommendations) {
            updated.recommendationData = { ...updated.recommendationData, results: data.updated_recommendations };
            updated.activeCardId = null;
            updated.cardDetails = {};
          }
          return updated;
        }),
      );
    } catch (err) {
      setSessions((prev) =>
        prev.map((s) =>
          s.id === session.id
            ? {
                ...s,
                chatMessages: [
                  ...s.chatMessages,
                  {
                    role: "assistant",
                    text: `Sorry, I encountered an error answering your question: ${
                      err instanceof Error ? err.message : "Unknown error"
                    }`,
                    sources: [],
                  },
                ],
              }
            : s,
        ),
      );
    } finally {
      setLoadingChat(false);
    }
  };

  return (
    <div className="bg-background text-foreground antialiased h-screen flex flex-col overflow-hidden">
      <Header
        showEdit={activeSession.view === "results"}
        onOpenSidebar={() => setSidebarOpen(true)}
        onReset={resetToForm}
      />

      <div className="flex flex-1 relative overflow-hidden">
        <Sidebar
          open={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
          sessions={sessions}
          activeSessionId={activeSessionId}
          onNewChat={newChat}
          onSwitchSession={switchSession}
          onDeleteSession={deleteSession}
        />

        {activeSession.view === "form" ? (
          <RecommendationForm
            formData={activeSession.formData}
            loading={loadingForm}
            error={formError}
            onChange={(patch) => updateActiveSession({ formData: { ...activeSession.formData, ...patch } })}
            onSubmit={submitForm}
          />
        ) : (
          <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 h-full overflow-hidden w-full">
            <RecommendationList
              data={activeSession.recommendationData}
              activeCardId={activeSession.activeCardId}
              cardDetails={activeSession.cardDetails}
              loadingCardDetail={loadingCardDetail}
              onToggle={toggleCard}
              onAsk={(item) =>
                sendChat(
                  `What are the step-by-step application requirements for the ${item.title} in ${item.country}?`,
                )
              }
            />
            <ChatPanel
              messages={activeSession.chatMessages}
              loading={loadingChat}
              input={chatInput}
              contextCountry={activeSession.activeContext.country}
              contextVisaType={activeSession.activeContext.visa_type}
              contextVisaId={activeSession.activeContext.visa_id}
              onInputChange={setChatInput}
              onSend={() => sendChat(chatInput)}
            />
          </div>
        )}
      </div>
    </div>
  );
}