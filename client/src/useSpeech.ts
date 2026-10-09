import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Web Speech input, with one deliberate trick.
 *
 * Final results arrive about a second after a person stops talking, which
 * on a display feels like being ignored. For the short commands people say
 * most — "yes", "stop", "what's today" — an interim result is already the
 * whole utterance, so it is dispatched early and the final one is dropped
 * if it says the same thing. Longer utterances wait for the final, because
 * an interim one is often half a sentence.
 */

const EARLY_DISPATCH_WORDS = 4;

interface SpeechResultLike {
  readonly isFinal: boolean;
  readonly length: number;
  item(index: number): { transcript: string };
  [index: number]: { transcript: string };
}

interface SpeechEventLike {
  readonly resultIndex: number;
  readonly results: { length: number; item(i: number): SpeechResultLike; [i: number]: SpeechResultLike };
}

interface RecognitionLike {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start(): void;
  stop(): void;
  onresult: ((event: SpeechEventLike) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
}

function recognitionClass(): (new () => RecognitionLike) | null {
  const holder = window as unknown as {
    SpeechRecognition?: new () => RecognitionLike;
    webkitSpeechRecognition?: new () => RecognitionLike;
  };
  return holder.SpeechRecognition ?? holder.webkitSpeechRecognition ?? null;
}

export function useSpeechInput(onUtterance: (text: string) => void): {
  supported: boolean;
  listening: boolean;
  toggle: () => void;
} {
  const [listening, setListening] = useState(false);
  const recognition = useRef<RecognitionLike | null>(null);
  const dispatched = useRef<string>("");

  const supported = recognitionClass() !== null;

  useEffect(() => {
    const Recognition = recognitionClass();
    if (!Recognition) return;
    const active = new Recognition();
    active.continuous = false;
    active.interimResults = true;
    active.lang = "en-US";

    active.onresult = (event: SpeechEventLike) => {
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i];
        if (!result) continue;
        const text = (result[0]?.transcript ?? "").trim();
        if (!text) continue;
        const words = text.split(/\s+/).length;
        const early = !result.isFinal && words <= EARLY_DISPATCH_WORDS;
        if (result.isFinal || early) {
          // Say each thing once: an early dispatch is followed by a final
          // result with the same words, and acting on both asks twice.
          if (text.toLowerCase() === dispatched.current.toLowerCase()) continue;
          dispatched.current = text;
          onUtterance(text);
        }
      }
    };
    active.onend = () => setListening(false);
    active.onerror = () => setListening(false);
    recognition.current = active;
    return () => {
      active.onresult = null;
      active.onend = null;
      active.onerror = null;
      try {
        active.stop();
      } catch {
        // already stopped
      }
    };
  }, [onUtterance]);

  const toggle = useCallback(() => {
    const active = recognition.current;
    if (!active) return;
    if (listening) {
      active.stop();
      setListening(false);
      return;
    }
    dispatched.current = "";
    try {
      active.start();
      setListening(true);
    } catch {
      setListening(false);
    }
  }, [listening]);

  return { supported, listening, toggle };
}
