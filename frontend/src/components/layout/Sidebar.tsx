import type { Session } from "@/types";

interface SidebarProps {
  open: boolean;
  onClose: () => void;
  sessions: Session[];
  activeSessionId: string;
  onNewChat: () => void;
  onSwitchSession: (id: string) => void;
  onDeleteSession: (id: string) => void;
}

function relativeTime(timestamp: number): string {
  const diffMs = Date.now() - timestamp;
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  return `${diffDay}d ago`;
}

export function Sidebar({
  open,
  onClose,
  sessions,
  activeSessionId,
  onNewChat,
  onSwitchSession,
  onDeleteSession,
}: SidebarProps) {
  const sorted = [...sessions].sort((a, b) => b.createdAt - a.createdAt);

  return (
    <>
      {open && (
        <div
          onClick={onClose}
          className="fixed inset-0 bg-foreground/40 backdrop-blur-sm z-40 transition-opacity"
        />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-50 w-72 bg-sidebar text-sidebar-foreground transform transition-transform duration-300 ease-out flex flex-col justify-between shadow-[var(--shadow-lift)] ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="p-4 space-y-6 overflow-y-auto flex-1 min-h-0">
          <div className="flex items-center justify-between pb-4 border-b border-sidebar-border">
            <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-sidebar-foreground/60">
              Navigation
            </span>
            <button
              type="button"
              aria-label="Close navigation menu"
              onClick={onClose}
              className="text-sidebar-foreground/70 hover:text-sidebar-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring rounded-lg p-1"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <button
            type="button"
            onClick={onNewChat}
            className="w-full py-2.5 px-4 bg-sidebar-primary hover:brightness-110 text-sidebar-primary-foreground rounded-xl font-semibold text-sm flex items-center justify-center gap-2 shadow-sm transition focus:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            New chat
          </button>

          <div>
            <h4 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-sidebar-foreground/60 mb-3">
              Recent conversations
            </h4>
            <ul className="space-y-1 text-sm">
              {sorted.map((session) => {
                const isActive = session.id === activeSessionId;
                return (
                  <li key={session.id} className="group relative">
                    <button
                      type="button"
                      onClick={() => onSwitchSession(session.id)}
                      className={`w-full flex items-center justify-between gap-2 px-3 py-2.5 rounded-xl text-left transition ${
                        isActive
                          ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium"
                          : "hover:bg-sidebar-accent/50 text-sidebar-foreground/90"
                      }`}
                    >
                      <span className="min-w-0 flex-1">
                        <span className="block truncate">{session.label}</span>
                        <span className="block text-[10px] text-sidebar-foreground/50 mt-0.5">
                          {relativeTime(session.createdAt)}
                        </span>
                      </span>

                      {isActive ? (
                        <span className="shrink-0 text-[10px] bg-sidebar-primary/20 text-sidebar-primary px-1.5 py-0.5 rounded-md">
                          Active
                        </span>
                      ) : (
                        <span
                          role="button"
                          tabIndex={0}
                          aria-label={`Delete conversation: ${session.label}`}
                          onClick={(e) => {
                            e.stopPropagation();
                            onDeleteSession(session.id);
                          }}
                          onKeyDown={(e) => {
                            if (e.key === "Enter" || e.key === " ") {
                              e.stopPropagation();
                              e.preventDefault();
                              onDeleteSession(session.id);
                            }
                          }}
                          className="shrink-0 opacity-0 group-hover:opacity-100 focus:opacity-100 text-sidebar-foreground/50 hover:text-destructive p-1 rounded-md transition-opacity"
                        >
                          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                            />
                          </svg>
                        </span>
                      )}
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        </div>

        {/* Placeholder user info until auth is wired up. */}
        <div className="p-4 border-t border-sidebar-border shrink-0">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-full bg-sidebar-accent flex items-center justify-center text-sidebar-accent-foreground font-semibold text-sm">
              JD
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-sidebar-foreground truncate">John Doe</p>
              <p className="text-xs text-sidebar-foreground/60 truncate">john.doe@example.com</p>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}