import { useCallback, useEffect, useRef, useState } from "react";
import { askHost, readCard, speak } from "./api";
import { CaptionBar } from "./CaptionBar";
import { CardHost } from "./CardHost";
import { DebugTimeline } from "./DebugTimeline";
import { beginTurn, debugEnabled, finishTurn, mark } from "./perf";
import type { HostTurn } from "./types";
import { useSpeechInput } from "./useSpeech";

/**
 * What to say when a turn does not come back.
 *
 * The host writes a sentence for the cases it knows about — the rate
 * limiter's "Easy — too many requests" among them — and that sentence is
 * better than anything this layer could invent. Anything that does not
 * read as something a person would say gets the generic.
 */
function sentenceFor(error: unknown): string {
  const text = error instanceof Error ? error.message : String(error);
  const trimmed = text.trim();
  const readsSpoken = /[.!?]$/.test(trimmed) && !/^[A-Za-z]*Error:/.test(trimmed);
  return readsSpoken ? trimmed : "I couldn't reach the server behind this. Try that again?";
}

export function App(): React.JSX.Element {
  const [heard, setHeard] = useState<string | null>(null);
  const [turn, setTurn] = useState<HostTurn | null>(null);
  const [cardHtml, setCardHtml] = useState<string | null>(null);
  const [cardContent, setCardContent] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState(false);
  const [typed, setTyped] = useState("");
  const [debugNonce, setDebugNonce] = useState(0);
  const [narrow, setNarrow] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    const check = (): void => setNarrow(window.innerWidth < window.innerHeight);
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);

  const send = useCallback(
    async (utterance: string) => {
      if (!utterance.trim() || busy) return;
      beginTurn(utterance);
      setBusy(true);
      setHeard(utterance);
      try {
        mark("request sent");
        const result = await askHost(utterance);
        mark("answer");
        setTurn(result);

        // A turn can ask for what is on screen to stay. "Yes" is about the
        // card being looked at; swapping it for a card about the
        // acknowledgement takes it away at the moment it is acted on.
        const keepsCard = result.cardAction === "keep";
        if (result.uiResourceUri && !keepsCard) {
          setCardContent(result.structuredContent ?? null);
          void readCard(result.uiResourceUri).then((html) => {
            mark("card html");
            setCardHtml(html);
          });
        } else if (result.structuredContent && keepsCard) {
          // Same card, new facts: pushed into the live document.
          setCardContent(result.structuredContent);
        }

        const blob = await speak(result.spoken);
        if (blob && audioRef.current) {
          mark("audio");
          audioRef.current.src = URL.createObjectURL(blob);
          void audioRef.current.play().catch(() => undefined);
        } else if (typeof window.speechSynthesis !== "undefined" && result.spoken) {
          // No voice service configured: the browser reads it instead,
          // which is what lets this repo run with no cloud account.
          mark("speech synthesis");
          const utterThis = new SpeechSynthesisUtterance(result.spoken);
          window.speechSynthesis.cancel();
          window.speechSynthesis.speak(utterThis);
        }
        finishTurn(result.timings);
      } catch (error) {
        // A failure is the thing on screen *and* the thing read out, like
        // any other answer. Writing only the caption left the live region
        // announcing the previous answer as though it were still current,
        // and anything watching it saw a display that never replied.
        const said = sentenceFor(error);
        setTurn({
          spoken: said,
          toolName: null,
          toolsCalled: [],
          uiResourceUri: null,
          structuredContent: null,
          timings: {},
        });
        finishTurn();
      } finally {
        setBusy(false);
        setDebugNonce((n) => n + 1);
      }
    },
    [busy],
  );

  const { supported: micSupported, listening, toggle } = useSpeechInput(
    useCallback((text: string) => void send(text), [send]),
  );

  const onSubmit = (event: React.FormEvent): void => {
    event.preventDefault();
    const utterance = typed.trim();
    setTyped("");
    void send(utterance);
  };

  return (
    <div className="stage">
      <div className="frame">
        {narrow && (
          <p className="narrow-notice">
            This is a smart-display layout. For the full experience, use a laptop or rotate to
            landscape.
          </p>
        )}

        <div className="cardarea" data-testid="cardarea">
          {cardHtml ? (
            <CardHost
              html={cardHtml}
              structuredContent={cardContent}
              onRendered={() => mark("card rendered")}
            />
          ) : (
            <div className="card-empty">
              Ask something. The answer appears here, with a card when the tool has one.
            </div>
          )}
          {debugEnabled() && <DebugTimeline nonce={debugNonce} />}
        </div>

        <CaptionBar heard={heard} said={turn?.spoken ?? null} />

        {/* The whole answer in one piece for a screen reader, announced
            once. The caption bar above is for reading; this is for
            hearing, and both have to be told when a turn fails. */}
        <p
          className="sr-only"
          data-testid="spoken"
          data-tools={(turn?.toolsCalled ?? []).join(",")}
          data-card={turn?.uiResourceUri ?? ""}
          aria-live="polite"
        >
          {turn?.spoken ?? ""}
        </p>

        <form className="controls" onSubmit={onSubmit}>
          <button
            type="button"
            className={listening ? "listening" : ""}
            onClick={toggle}
            disabled={!micSupported || busy}
            data-testid="speak"
          >
            {listening ? "Listening" : "Speak"}
          </button>
          <input
            data-testid="typed-input"
            value={typed}
            onChange={(event) => setTyped(event.target.value)}
            placeholder="or type it"
            disabled={busy}
          />
          <button type="submit" disabled={busy || !typed.trim()} data-testid="typed-send">
            Send
          </button>
        </form>

        <audio ref={audioRef} hidden />
      </div>
    </div>
  );
}
