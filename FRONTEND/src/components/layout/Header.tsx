interface HeaderProps {
  showEdit: boolean;
  onOpenSidebar: () => void;
  onReset: () => void;
}

export function Header({ showEdit, onOpenSidebar, onReset }: HeaderProps) {
  return (
    <header className="bg-surface/85 backdrop-blur-xl border-b border-border shrink-0 z-30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <button
            type="button"
            aria-label="Open navigation menu"
            onClick={onOpenSidebar}
            className="p-2 text-muted-foreground hover:text-foreground hover:bg-muted rounded-xl transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <button
            type="button"
            onClick={onReset}
            className="flex items-center gap-2.5 cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-ring/50 rounded-xl pr-2"
          >
            <div className="w-9 h-9 canopy-gradient rounded-xl flex items-center justify-center shadow-[var(--shadow-soft)]">
              <svg className="w-5 h-5 text-primary-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 002 2h1.5a2.5 2.5 0 002.5-2.5V11a2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064" />
              </svg>
            </div>
            <span className="font-display font-bold text-lg sm:text-xl tracking-tight text-foreground">
              Immigration<span className="text-primary"> Assistant</span>
            </span>
          </button>
        </div>

        {showEdit && (
          <button
            type="button"
            onClick={onReset}
            className="hidden sm:flex items-center gap-2 text-xs font-semibold text-secondary-foreground hover:text-primary-foreground bg-secondary hover:bg-primary px-3.5 py-2 rounded-xl transition focus:outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
            <span>Edit criteria</span>
          </button>
        )}
      </div>
    </header>
  );
}
