# Immigration Compass

Lovable Build Prompt — Immigration Assistant Frontend

Copy everything below into Lovable as your project prompt.

Build a React + Tailwind CSS frontend for an "Immigration Assistant" chatbot. It has two views inside one single-page app: a Recommendation Form and a Split-Screen Results view (recommendation cards on the left, a chat assistant on the right). No routing library needed — toggle between views with local state (view: 'form' | 'results').

1. Tech stack

React (functional components + hooks), TypeScript preferred

Tailwind CSS for styling

No Alpine.js — this is a straight React port of an existing Alpine.js prototype

dompurify for sanitizing any HTML we render (see Security section — this is required, not optional)

crypto.randomUUID() (native, no library) for session IDs

2. Design system (match exactly)

Tailwind theme extension:

colors: {
  brand: {
    900: '#0f172a',
    800: '#1e293b',
    600: '#2563eb',
    500: '#3b82f6',
    emerald: '#10b981',
  }
}


Base body: bg-slate-50 text-slate-800, sans-serif, antialiased, full height, no page-level scroll (overflow-hidden on the root, individual panels scroll internally).

3. Layout — Top navigation (always visible)

Fixed header, h-16, white background, bottom border.

Left: hamburger icon button that opens a slide-in sidebar; brand mark (rounded dark-navy square with an emerald icon) + wordmark "Immigration AssistantAI" (AI in brand blue). Clicking the brand resets to the form view.

Center-right: an "Edit Scenario Criteria" pill button, only visible when view === 'results', hidden on mobile (hidden sm:flex), clicking it resets to the form view.

4. Collapsible sidebar

Fixed left drawer, w-72, dark navy (bg-brand-900), slides in/out with a transform + backdrop overlay on mobile. Contains:

Header row: "Navigation" label + close (X) button

"New Assessment" button (brand blue) that resets to the form view and closes the sidebar

"Recent Assessments" list — for now just a static "Current Profile / Active" entry (leave a comment noting this should eventually be dynamic)

Footer: user avatar initials, name, email (placeholder user info for now)

5. View 1 — Recommendation form

Centered card, max-width ~3xl, white, rounded-2xl, shadow. Heading "Find Your Ideal Destination" + subtext. Form fields (2-column grid on desktop, stacked on mobile):

Field Type Notes Primary Goal / Purpose select Options: Any Purpose, Work / Employment, Higher Education / Study, Permanent Residency, Business / Investment Target Countries text input Comma-separated, e.g. "Canada, Germany, Australia" Education Level select Master's/Doctorate, Bachelor's, Associate/Diploma, High School Available Budget number input Prefixed with "Rs." currency label Language Test text input e.g. IELTS, TOEFL, TEF Language Score text input e.g. "8.0" or "CLB 9"

Submit button: full-width, dark navy, shows a spinner + "Analyzing..." while loading, disabled during submit.

On submit, split the countries input into a trimmed array (or null if empty) and call the recommend API (see API contract below). On success, populate results and switch to the results view with an initial assistant welcome message. On failure, show an inline error state near the form (not a browser alert() — see Security section).

6. View 2 — Split screen (results)

grid grid-cols-1 lg:grid-cols-12, full height, no page scroll — each panel scrolls independently.

Left panel (recommendation cards) — lg:col-span-6 xl:col-span-5

Header row: "Recommended Routes" title + subtext (shows a "relaxed match" message from the API if present) + a pill badge showing the match count.

Empty state card if there are zero results.

One card per result, each an accordion:

Collapsed header (clickable): country tag + visa-type tag, title, 2-line-clamped summary, a "Expand Full Policy Details →" / "Collapse Details" toggle label, and an "Official Source" external link (stop propagation so it doesn't also toggle the card).

Expanded body (lazy-loaded on first expand, then cached client-side so re-expanding doesn't refetch): loading spinner while fetching, then conditionally-rendered sections for Eligibility Criteria (bullet list), Required Documents (bullet list), Application Process (numbered list), Government Fees & Costs (application fee / total estimated cost + currency / processing time / validity), Important Notes (bullet list), and a "Last verified" timestamp. Ends with an "Ask AI Assistant about this visa" button that pre-fills and sends a chat question using that card's title/country as context.

Right panel (chat) — lg:col-span-6 xl:col-span-7

Header: AI avatar, "Immigration Assistant" title, and a small line showing current context ("Context: Canada (Work Permit)" or "General Context" when no card is expanded).

Scrollable message stream:

Assistant messages: left-aligned bubble with AI avatar, rendered text with inline citation badges (see Security section for how citations must be rendered safely), and a "Sources" row of small chips below the message when sources exist.

User messages: right-aligned dark bubble, plain text.

Loading state: animated spinner bubble with "Searching knowledge base and generating answer..." while waiting on a response.

Auto-scroll to the bottom whenever a new message is added or loading state changes.

Input row at the bottom: text input + submit icon button, both disabled while a request is in flight, submit disabled if the input is empty/whitespace.

7. State shape (React, e.g. useState/useReducer or a small context)

sessionId: string;                 // crypto.randomUUID(), generated once on mount
view: 'form' | 'results';
sidebarOpen: boolean;
loadingForm: boolean;
loadingChat: boolean;
loadingCardDetail: boolean;
formData: {
  purpose: string;
  countriesInput: string;
  education_level: string;
  language_test: string;
  language_score: string;
  budget: number | null;
  budget_currency: string;         // e.g. "PKR"
};
recommendationData: {
  relaxed: boolean;
  message: string | null;
  results: VisaRecommendation[];
};
activeCardId: string | null;
cardDetails: Record<string, VisaDetail>;   // cache keyed by visa id
activeContext: { country: string | null; visa_type: string | null };
chatInput: string;
chatMessages: { role: 'user' | 'assistant'; text: string; sources?: Source[] }[];


8. API contract

Base URL must come from an environment variable (VITE_API_BASE_URL or equivalent), never hardcoded, with a sensible local-dev fallback. All requests use credentials: 'omit' unless the backend specifically requires cookies, and all bodies are JSON.

POST {API_BASE_URL}/recommend Request:

{
  "session_id": "uuid",
  "countries": ["Canada", "Germany"] | null,
  "purpose": "Work" | null,
  "education_level": "master" | null,
  "language_test": "IELTS" | null,
  "language_score": "8.0" | null,
  "budget": 25000 | null,
  "budget_currency": "PKR" | null
}


Response:

{
  "relaxed": false,
  "message": "string | null",
  "results": [
    { "id": "string", "country": "string", "visa_type": "string", "title": "string", "summary": "string", "source_url": "string | null" }
  ]
}


GET {API_BASE_URL}/visa-detail/{id} Response:

{
  "eligibility": ["string"],
  "required_documents": ["string"],
  "application_process": ["string"],
  "application_fee": "string | null",
  "total_estimated_cost": "number | null",
  "cost_currency": "string | null",
  "processing_time": "string | null",
  "validity": "string | null",
  "important_notes": ["string"],
  "last_verified_date": "string | null"
}


POST {API_BASE_URL}/ask Request:

{
  "session_id": "uuid",
  "query": "string",
  "context_country": "string | null",
  "context_visa_type": "string | null"
}


Response:

{
  "answer": "string",
  "sources": [ { "title": "string", "source_url": "string", "last_verified_date": "string | null" } ],
  "updated_recommendations": [ /* same shape as results, optional */ ]
}


If updated_recommendations is present, replace recommendationData.results with it, collapse any open card, and clear the detail cache.

9. Citation rendering — inline [1], [2] markers in assistant answers

The assistant's answer text contains markers like [1], [2] that map by position to the sources array (1-indexed). Each marker should render as a small superscript badge that shows a tooltip with the source title (and "Verified {date}" if present) and links to source_url in a new tab.

10. Security requirements (critical — do not skip these)

This app renders AI-generated text and externally-sourced URLs, so treat all of it as untrusted input:

Never use dangerouslySetInnerHTML on raw model output. Build the citation-badge markup with dompurify's sanitize() before injecting it, and configure it to allow only the specific tags/attributes you need (a, span, href, target, rel, class, data-tooltip) — no <script>, no event-handler attributes.

Validate/allowlist URLs before using them in href. Any source_url coming from the API must be checked to start with http:// or https:// before being rendered as a link; reject or strip anything using javascript:, data:, or other schemes. Do this for both the citation badges and the "Official Source" card links.

Always set rel="noopener noreferrer" (and target="_blank") on every externally-sourced link.

No secrets in the frontend. The API base URL is fine as a public env var; do not embed API keys, tokens, or credentials in client code. If the backend needs auth, use a short-lived token fetched via a secure call, not a hardcoded key.

Escape/plain-text everything else. All other dynamic text (titles, summaries, eligibility bullets, chat text itself) should be rendered as plain React text content ({value}), never dangerouslySetInnerHTML — React escapes this by default, which is what you want.

Client-side input validation, not trust. Validate form inputs (e.g. budget must be a non-negative number) before sending, but treat this as UX only — real validation must happen server-side; don't assume the frontend's checks are a security boundary.

No alert() for errors. Replace all error handling with inline UI state (toast or inline message) so errors can't be used to inject unexpected browser dialogs and so the UI stays testable/accessible.

HTTPS only in production. The API base URL env var should default to an https:// origin outside local dev.

Don't persist sensitive data in localStorage/sessionStorage. The session ID can live in memory (state) for the life of the tab; if you do want it to survive a refresh, that's the only thing that should go in storage — never chat content or personal form data (education, budget, etc.).

CORS/backend note to leave as a comment in code: the backend should restrict Access-Control-Allow-Origin to the deployed frontend's actual domain, not *, since this app sends session identifiers.

11. Responsiveness & accessibility

Mobile: sidebar becomes an overlay drawer with backdrop; results grid stacks to a single column; "Edit Scenario Criteria" button hides on small screens (it's redundant with the hamburger menu, but keep the hamburger action working).

All icon-only buttons need aria-labels (hamburger, close sidebar, chat send).

Form inputs need associated <label>s (already implied by the field table above).

Focus states on interactive elements (inputs, buttons) should be visible, matching the blue focus ring style used in the original.

12. Component structure suggestion

src/
  App.tsx
  components/
    layout/Header.tsx
    layout/Sidebar.tsx
    form/RecommendationForm.tsx
    results/RecommendationCard.tsx
    results/RecommendationList.tsx
    chat/ChatPanel.tsx
    chat/ChatMessage.tsx
    chat/CitationBadge.tsx
  lib/api.ts        // fetch wrappers for /recommend, /visa-detail, /ask
  lib/sanitize.ts    // dompurify + URL-allowlist helpers
  types.ts


Build this as a clean, production-quality React app matching the visual design described above exactly (colors, spacing, card styles, chat bubble styles), with the security requirements in section 10 treated as hard constraints, not nice-to-haves.Reference the attached HTML file for exact visual styling, spacing, and copy — replicate it precisely in React, but apply the security fixes and API structure described above

This project was built with [Lovable](https://lovable.dev).

## Build with Lovable

Continue developing this project in the [Lovable editor](https://lovable.dev/projects/1ef0783c-fcc9-4f19-9906-b77d4494864d).

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Stay in sync**: every change made in Lovable is committed straight to this repository.
- **Full ownership**: this code is yours. Push to `main` on GitHub and your changes sync back into Lovable, ready for your next prompt.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
npm run dev
```
