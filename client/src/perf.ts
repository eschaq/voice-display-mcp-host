/**
 * Marks for one turn, shown by ?debug=1.
 *
 * Latency on a display is not one number: the card can be up a second
 * before the words finish, and which half is slow decides what to fix. So
 * each step is marked as it happens and the whole timeline is readable on
 * screen rather than only in a harness.
 */

export interface Mark {
  label: string;
  at: number;
}

let marks: Mark[] = [];
let startedAt = 0;

export function beginTurn(utterance: string): void {
  startedAt = performance.now();
  marks = [{ label: `heard: ${utterance.slice(0, 40)}`, at: 0 }];
}

export function mark(label: string): void {
  if (!startedAt) return;
  marks.push({ label, at: performance.now() - startedAt });
}

export function finishTurn(serverTimings: Record<string, number> = {}): void {
  for (const [label, seconds] of Object.entries(serverTimings)) {
    marks.push({ label: `server ${label}`, at: seconds * 1000 });
  }
  mark("done");
}

export function timeline(): Mark[] {
  return [...marks];
}

export function debugEnabled(): boolean {
  try {
    return new URLSearchParams(window.location.search).get("debug") === "1";
  } catch {
    return false;
  }
}
