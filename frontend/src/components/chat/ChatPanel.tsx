import { useEffect, useRef } from "react";
import type { ChatMessage as ChatMessageType } from "@/types";
import { ChatMessage } from "./ChatMessage";

interface Props {
  messages: ChatMessageType[];
  loading: boolean;
  input: string;
  contextCountry: string | null;
  contextVisaType: string | null;
  contextVisaId: string | null;      // NEW
  onInputChange: (value: string) => void;
  onSend: () => void;
}

const SUGGESTIONS = [
  "What documents do I need?",
  "How long does processing take?",
  "Can my family come with me?",
];

export function ChatPanel({
  messages,
  loading,
  input,
  contextCountry,
  contextVisaType,
  contextVisaId,                     
  onInputChange,
  onSend,
}: Props) {
  const streamRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = streamRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, loading]);

  return (
    <section className="lg:col-span-6 xl:col-span-7 h-full flex flex-col min-h-0 bg-surface">
      <div className="px-5 py-4 border-b border-border flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl canopy-gradient flex items-center justify-center text-primary-foreground">
            <svg className="w-4.5 h-4.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
            </svg>
          </div>
          <div>
            <h3 className="font-display text-sm font-bold text-foreground">Immigration assistant</h3>
            <p className="text-[11px] text-muted-foreground">
              {contextCountry ? (
                <span className="inline-flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-accent" />
                  Focused on {contextCountry} · {contextVisaType}
                </span>
              ) : (
                "General context — expand a route to focus the conversation"
              )}
            </p>
          </div>
        </div>
      </div>

      <div ref={streamRef} className="flex-1 overflow-y-auto p-4 sm:p-6 bg-surface">
        {messages.map((msg, index) => (
          <ChatMessage key={index} msg={msg} />
        ))}

        {loading && (
          <div className="flex items-start gap-3 max-w-2xl">
            <div className="w-8 h-8 rounded-xl canopy-gradient flex-shrink-0 flex items-center justify-center text-primary-foreground mt-0.5">
              <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
            </div>
            <p className="text-sm text-muted-foreground animate-pulse mt-1.5">
              Searching official sources…
            </p>
          </div>
        )}
      </div>

      <div className="p-4 border-t border-border bg-surface shrink-0 space-y-3">
        {messages.length <= 1 && !loading && (
          <div className="flex flex-wrap gap-2">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => onInputChange(s)}
                className="text-[11px] px-3 py-1.5 rounded-full border border-border bg-surface-sunken text-muted-foreground hover:text-primary hover:border-primary/40 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
              >
                {s}
              </button>
            ))}
          </div>
        )}
        <form
          className="relative flex items-center"
          onSubmit={(e) => {
            e.preventDefault();
            onSend();
          }}
        >
          <label htmlFor="chat-input" className="sr-only">
            Ask the immigration assistant a question
          </label>
          <input
            id="chat-input"
            type="text"
            value={input}
            disabled={loading}
            onChange={(e) => onInputChange(e.target.value)}
            placeholder="Ask about visas, processing times, or requirements…"
            className="w-full rounded-2xl border border-input bg-surface-sunken py-3.5 pl-4 pr-14 text-sm text-foreground placeholder:text-muted-foreground/70 transition focus:border-ring focus:bg-surface focus:outline-none focus:ring-4 focus:ring-ring/15"
          />
          <button
            type="submit"
            aria-label="Send message"
            disabled={loading || !input.trim()}
            className="absolute right-2 w-9 h-9 flex items-center justify-center text-primary-foreground canopy-gradient hover:brightness-110 disabled:opacity-40 rounded-xl transition focus:outline-none focus-visible:ring-4 focus-visible:ring-ring/30"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
            </svg>
          </button>
        </form>
      </div>
    </section>
  );
}
