import { useEffect, useRef } from "react";
import { AppBridge, PostMessageTransport } from "@modelcontextprotocol/ext-apps/app-bridge";
import { callTool } from "./api";

/**
 * Renders an MCP App card in a sandboxed iframe and speaks the host side
 * of the postMessage dialect, using AppBridge from the official package.
 *
 * The sandbox has `allow-scripts` and deliberately not `allow-same-origin`:
 * the card gets an opaque origin and cannot reach this page, which is the
 * isolation the extension's security model exists to provide. It is also
 * why the card cannot fetch its own fonts — see `resourceDomains` in the
 * README — and why a tool call it makes is forwarded through here.
 */
export function CardHost({
  html,
  structuredContent,
  onRendered,
}: {
  html: string | null;
  structuredContent: Record<string, unknown> | null;
  /** Fired the first time the card reports its size, which the bridge
   *  sends immediately after a render. It is the only render signal a host
   *  can have: the iframe's DOM is unreadable from here. */
  onRendered?: () => void;
}): React.JSX.Element | null {
  const frameRef = useRef<HTMLIFrameElement | null>(null);
  const bridgeRef = useRef<AppBridge | null>(null);
  // The latest facts, readable by the mount effect without being a
  // dependency of it. Making them a dependency meant every new answer
  // rewrote `srcdoc`, which throws the card's document away and builds it
  // again: the card goes blank, then redraws when the data is pushed to
  // the new document. On a 16:9 stage that reads as a flicker.
  const contentRef = useRef<Record<string, unknown> | null>(structuredContent);
  contentRef.current = structuredContent;

  useEffect(() => {
    const iframe = frameRef.current;
    if (!iframe || !html) return;

    let cancelled = false;
    const timers: ReturnType<typeof setTimeout>[] = [];

    // Attach the load listener before assigning srcdoc: the load can
    // complete first, and a listener added afterwards never fires.
    const loaded = new Promise<void>((resolve) => {
      iframe.addEventListener("load", () => resolve(), { once: true });
    });
    iframe.srcdoc = html;

    void (async () => {
      await loaded;
      if (cancelled || !iframe.contentWindow) return;

      const active = new AppBridge(null, { name: "voice-display", version: "1.0.0" }, {});
      bridgeRef.current = active;

      active.oncalltool = async (params) => {
        try {
          const result = await callTool(
            params.name,
            (params.arguments ?? {}) as Record<string, unknown>,
          );
          return {
            content: result.content as { type: "text"; text: string }[],
            structuredContent: result.structuredContent,
          };
        } catch (error) {
          return {
            content: [{ type: "text" as const, text: String(error) }],
            isError: true,
          };
        }
      };

      // The card's height report is not applied: every card gets the same
      // 16:9 region and is built to fit it in container units. What the
      // notification is used for is its timing — the bridge sends it
      // directly after a render.
      let reported = false;
      active.onsizechange = () => {
        if (!reported) {
          reported = true;
          onRendered?.();
        }
        return undefined;
      };

      // Push the data rather than negotiate for the right to. A tool
      // result is idempotent — the card just renders again — so it goes
      // out as soon as possible, again when the card says it initialised,
      // and once more shortly after for a card that was slow to come up.
      // Gating the first send on the handshake is a deadlock waiting to
      // happen, and it happens: a card whose initialize reply goes astray
      // sits on its empty shell forever.
      const push = (): void => {
        if (cancelled) return;
        void active
          .sendToolResult({
            content: [{ type: "text" as const, text: "" }],
            // Read at send time, not at mount time: the facts can land
            // between the iframe loading and the bridge connecting.
            structuredContent: contentRef.current ?? {},
          })
          .catch(() => undefined);
      };

      active.oninitialized = () => push();

      const transport = new PostMessageTransport(iframe.contentWindow, iframe.contentWindow);
      await active.connect(transport);
      if (cancelled) return;

      push();
      timers.push(setTimeout(push, 1200));
    })();

    return () => {
      cancelled = true;
      timers.forEach(clearTimeout);
      bridgeRef.current = null;
    };
  }, [html, onRendered]);

  // New facts for a card already up. The same document renders again — a
  // tool result is idempotent — rather than being rebuilt.
  useEffect(() => {
    const bridge = bridgeRef.current;
    if (!bridge || !structuredContent) return;
    void bridge
      .sendToolResult({
        content: [{ type: "text" as const, text: "" }],
        structuredContent,
      })
      .catch(() => undefined);
  }, [structuredContent]);

  if (!html) return null;

  return <iframe ref={frameRef} className="card-frame" title="card" sandbox="allow-scripts" />;
}
