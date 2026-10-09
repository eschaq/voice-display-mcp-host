/**
 * Who this browser is, for the length of this browser.
 *
 * Not an identity and not authentication: a random id the page mints for
 * itself so the host can keep one visitor's conversation and rate limit
 * out of another's. A shared demo link is one server and many people, and
 * without this the second person inherits the first one's session.
 *
 * Every storage access is wrapped, because a private window, blocked site
 * data or an embedded preview can all throw on the first read — and a
 * display that will not load because it cannot remember a random string is
 * a worse failure than forgetting it.
 */

const VISITOR_KEY = "voice-display.visitorId";

let inMemory: string | null = null;

function randomId(): string {
  try {
    if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
      return crypto.randomUUID();
    }
  } catch {
    // fall through to the arithmetic one
  }
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

export function visitorId(): string {
  if (inMemory) return inMemory;
  try {
    const stored = window.localStorage.getItem(VISITOR_KEY);
    if (stored) {
      inMemory = stored;
      return stored;
    }
  } catch {
    // storage is unavailable; the per-tab id below is still better than none
  }
  const minted = randomId();
  inMemory = minted;
  try {
    window.localStorage.setItem(VISITOR_KEY, minted);
  } catch {
    // keep it in memory for this tab and carry on
  }
  return minted;
}
