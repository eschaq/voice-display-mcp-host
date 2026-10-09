import { visitorId } from "./session";
import type { HostTurn } from "./types";

/** Send one utterance to the host and get the turn back. */
export async function askHost(utterance: string): Promise<HostTurn> {
  const response = await fetch("/turn", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ utterance, visitorId: visitorId() }),
  });
  const payload = (await response.json()) as HostTurn & { error?: string };
  if (!response.ok && !payload.spoken) {
    // The host writes a sentence for the cases it knows about — a rate
    // limit, a server it cannot reach — and that sentence is better than
    // anything this layer could invent, so it is thrown as the message.
    throw new Error(payload.error ?? `host returned ${response.status}`);
  }
  return payload;
}

/**
 * The answer as audio, when the host has a voice configured.
 *
 * 204 means it does not, and the caller falls back to the browser's own
 * speechSynthesis — which is how this runs with no cloud account.
 */
export async function speak(text: string): Promise<Blob | null> {
  try {
    const response = await fetch("/speak", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (response.status === 204 || !response.ok) return null;
    return await response.blob();
  } catch {
    return null;
  }
}

/**
 * A card's HTML, fetched once per uri and remembered.
 *
 * A card's document is static — the same html every time, with only the
 * data pushed into it changing. Fetching it after the answer lands puts a
 * round trip between having something to draw and drawing it.
 */
const cardCache = new Map<string, Promise<string | null>>();

export function readCard(uri: string): Promise<string | null> {
  const cached = cardCache.get(uri);
  if (cached) return cached;
  const pending = fetchCard(uri).then((html) => {
    if (html === null) cardCache.delete(uri); // don't cache a failure
    return html;
  });
  cardCache.set(uri, pending);
  return pending;
}

async function fetchCard(uri: string): Promise<string | null> {
  try {
    const response = await fetch(`/card?uri=${encodeURIComponent(uri)}`);
    if (!response.ok) return null;
    return await response.text();
  } catch {
    return null;
  }
}

/**
 * A tool call made by a card, forwarded to the MCP server.
 *
 * The card has an opaque origin and no network of its own, so the display
 * carries the call. This is what lets a card poll real progress instead of
 * animating something that looks like it.
 */
export async function callTool(
  name: string,
  args: Record<string, unknown>,
): Promise<{ content: unknown[]; structuredContent?: Record<string, unknown> }> {
  const response = await fetch("/turn", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ utterance: `__tool__:${name}`, tool: name, arguments: args, visitorId: visitorId() }),
  });
  const payload = (await response.json()) as HostTurn;
  return {
    content: [{ type: "text", text: payload.spoken }],
    structuredContent: payload.structuredContent ?? undefined,
  };
}
