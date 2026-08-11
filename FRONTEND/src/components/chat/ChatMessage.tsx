import type { ChatMessage as ChatMessageType } from "@/types";
import { formatAnswerWithCitations } from "@/lib/sanitize";

export function ChatMessage({ msg }: { msg: ChatMessageType }) {
  if (msg.role === "user") {
    return (
      <div className="flex items-start justify-end mb-4">
        <div className="bg-primary text-primary-foreground px-4 py-3 rounded-2xl rounded-tr-md text-sm max-w-md shadow-[var(--shadow-soft)]">
          <p className="whitespace-pre-line">{msg.text}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-start gap-3 max-w-2xl mb-4">
      <div className="w-8 h-8 rounded-xl canopy-gradient flex-shrink-0 flex items-center justify-center text-primary-foreground mt-0.5">
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 002 2h1.5a2.5 2.5 0 002.5-2.5V11a2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064" />
        </svg>
      </div>
      <div className="flex-1 min-w-0 text-sm text-foreground/85 space-y-2">
        {/* Sanitized with DOMPurify (allowlisted tags/attrs only) so AI output can never inject markup. */}
        <p
          className="whitespace-pre-line leading-relaxed"
          dangerouslySetInnerHTML={{
            __html: formatAnswerWithCitations(msg.text, msg.sources),
          }}
        />
        {msg.sources && msg.sources.length > 0 && (
          <div className="pt-1 text-[11px] text-muted-foreground">
            <span className="font-semibold text-foreground">Sources</span>
            <div className="flex flex-wrap gap-1.5 mt-1.5">
              {msg.sources.map((src, i) => (
                <span
                  key={i}
                  className="bg-secondary border border-border px-2 py-1 rounded-lg text-[10px] text-secondary-foreground"
                >
                  {src.title || "Official source"}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
