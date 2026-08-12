interface SidebarProps {
  open: boolean;
  onClose: () => void;
  onNewAssessment: () => void;
}

export function Sidebar({ open, onClose, onNewAssessment }: SidebarProps) {
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
        <div className="p-4 space-y-6 overflow-y-auto">
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
            onClick={onNewAssessment}
            className="w-full py-2.5 px-4 bg-sidebar-primary hover:brightness-110 text-sidebar-primary-foreground rounded-xl font-semibold text-sm flex items-center justify-center gap-2 shadow-sm transition focus:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            New assessment
          </button>

          <div>
            <h4 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-sidebar-foreground/60 mb-3">
              Recent assessments
            </h4>
            {/* TODO: make this list dynamic once assessment history is persisted server-side. */}
            <ul className="space-y-1 text-sm">
              <li>
                <div className="flex items-center justify-between px-3 py-2.5 rounded-xl bg-sidebar-accent text-sidebar-accent-foreground font-medium">
                  <span className="truncate">Current profile</span>
                  <span className="text-[10px] bg-sidebar-primary/20 text-sidebar-primary px-1.5 py-0.5 rounded-md">
                    Active
                  </span>
                </div>
              </li>
            </ul>
          </div>
        </div>

        {/* Placeholder user info until auth is wired up. */}
        <div className="p-4 border-t border-sidebar-border">
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
