/** One turn, as the host returns it. */
export interface HostTurn {
  spoken: string;
  toolName: string | null;
  /** Every tool called this turn, in call order. */
  toolsCalled: string[];
  uiResourceUri: string | null;
  /**
   * Whether this turn's card replaces what is on screen or leaves it.
   *
   * A new question replaces; a bare "yes" or a sign-off keeps, because both
   * are about the thing already showing. Absent from an older host, which
   * is read as "replace".
   */
  cardAction?: "keep" | "replace";
  structuredContent: Record<string, unknown> | null;
  /** Server-side spans in seconds, for the ?debug=1 overlay. */
  timings: Record<string, number>;
  visitorId?: string;
  error?: string;
}
