const ALLOWED_PROTOCOLS = new Set(["https:"]);

export function safeExternalUrl(value: string | null | undefined): string | null {
  if (!value) {
    return null;
  }

  try {
    const url = new URL(value.trim());
    if (!ALLOWED_PROTOCOLS.has(url.protocol) || !url.hostname) {
      return null;
    }
    return url.href;
  } catch {
    return null;
  }
}
