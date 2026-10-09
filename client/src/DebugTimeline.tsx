import { timeline } from "./perf";

/** The last turn's marks, on screen, behind ?debug=1. */
export function DebugTimeline({ nonce }: { nonce: number }): React.JSX.Element | null {
  const marks = timeline();
  if (!marks.length) return null;
  return (
    <div className="debug" data-testid="debug" data-nonce={nonce}>
      {marks.map((entry) => `${entry.at.toFixed(0).padStart(5)}ms  ${entry.label}`).join("\n")}
    </div>
  );
}
