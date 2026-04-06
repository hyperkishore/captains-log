/**
 * Security utilities for sanitizing user-generated content
 */

/**
 * Sanitize URLs to prevent XSS attacks via javascript: and data: protocols
 * @param url - The URL to sanitize
 * @returns The sanitized URL or null if dangerous
 */
export function sanitizeUrl(url: string | null | undefined): string | null {
  if (!url) return null;

  const trimmed = url.trim();
  if (!trimmed) return null;

  const lower = trimmed.toLowerCase();

  // Block dangerous protocols
  const dangerousProtocols = ['javascript:', 'data:', 'vbscript:', 'file:'];
  for (const protocol of dangerousProtocols) {
    if (lower.startsWith(protocol)) {
      console.warn(`[Security] Blocked dangerous URL protocol: ${protocol}`);
      return null;
    }
  }

  // Allow only safe protocols
  const safeProtocols = ['http://', 'https://', 'mailto:', 'tel:', 'ftp://'];
  const hasSafeProtocol = safeProtocols.some(protocol => lower.startsWith(protocol));

  // If no protocol, assume relative URL (safe)
  // If has protocol but not safe, block it
  if (lower.includes(':') && !hasSafeProtocol) {
    console.warn(`[Security] Blocked URL with unknown protocol: ${trimmed}`);
    return null;
  }

  return trimmed;
}

/**
 * Sanitize text content to prevent XSS (React does this by default, but useful for edge cases)
 * @param text - The text to sanitize
 * @returns The sanitized text
 */
export function sanitizeText(text: string | null | undefined): string {
  if (!text) return '';

  // Remove any HTML tags
  return text.replace(/<[^>]*>/g, '');
}

/**
 * Truncate long strings to prevent UI overflow and potential DoS
 * @param text - The text to truncate
 * @param maxLength - Maximum length (default 1000)
 * @returns The truncated text
 */
export function truncateText(text: string | null | undefined, maxLength = 1000): string {
  if (!text) return '';
  if (text.length <= maxLength) return text;

  return text.substring(0, maxLength) + '...';
}
