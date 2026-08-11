import DOMPurify from "dompurify";
import type { Source } from "@/types";

/**
 * Allowlist URL schemes. Anything that is not http(s) (javascript:, data:, etc.)
 * is rejected so it can never end up in an href.
 */
export function safeUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  const trimmed = url.trim();
  if (!/^https?:\/\//i.test(trimmed)) return null;
  try {
    const parsed = new URL(trimmed);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") return null;
    return parsed.toString();
  } catch {
    return null;
  }
}

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/**
 * Turns [1], [2] markers into sanitized citation badges.
 * The whole answer text is HTML-escaped first, then only our own markup is
 * added, then DOMPurify strips anything outside the tiny allowlist below.
 */
export function formatAnswerWithCitations(
  text: string,
  sources?: Source[],
): string {
  const escaped = escapeHtml(text ?? "");
  if (!sources || sources.length === 0) return sanitize(escaped);

  const withBadges = escaped.replace(/\[(\d+)\]/g, (match, num: string) => {
    const src = sources[parseInt(num, 10) - 1];
    if (!src) return match;
    const url = safeUrl(src.source_url);
    const title = escapeHtml(src.title || "Source");
    const verified = src.last_verified_date
      ? ` — Verified ${escapeHtml(src.last_verified_date)}`
      : "";
    const tooltip = `${title}${verified}`;
    if (!url) {
      return `<span class="citation-badge" data-tooltip="${tooltip}">${escapeHtml(num)}</span>`;
    }
    return `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer" class="citation-badge" data-tooltip="${tooltip}">${escapeHtml(num)}</a>`;
  });

  return sanitize(withBadges);
}

export function sanitize(html: string): string {
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: ["a", "span"],
    ALLOWED_ATTR: ["href", "target", "rel", "class", "data-tooltip"],
    ALLOWED_URI_REGEXP: /^https?:\/\//i,
  });
}
