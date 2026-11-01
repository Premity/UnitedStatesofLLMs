import fixture from "@/fixtures/sample-run.json";
import type { Turn, Verdict } from "@/types";

/**
 * Replays a recorded debate from a fixture, with no backend.
 *
 * A real debate takes minutes because four models generate in sequence, and
 * three of the four need API keys or a local GPU. That makes the courtroom
 * almost impossible to iterate on. Replay feeds the store the same events the
 * SSE stream would, so the UI can be developed and demonstrated offline.
 *
 * The fixture is `scripts/generate_fixture.py` output — real payload shapes
 * from the Pydantic models, invented prose. `scripts/record_fixture.py`
 * overwrites it with a genuine recording in the same format.
 *
 * Enabled by `?replay=1` or `VITE_REPLAY=1`. Never used in production: the
 * check is explicit rather than a dev-mode default, so a built bundle cannot
 * show fabricated proceedings by accident.
 */

/** One SSE event as the fixture stores it: payload parsed, not a JSON string. */
export interface ReplayEvent {
  event: "start" | "turn" | "verdict" | "error" | "done";
  data: unknown;
}

export const replayEvents = fixture as ReplayEvent[];

/** Whether replay mode is on. Query parameter wins over the build-time flag. */
export function isReplayEnabled(search: string = window.location.search): boolean {
  const param = new URLSearchParams(search).get("replay");
  if (param !== null) return param !== "0" && param !== "false";
  return import.meta.env.VITE_REPLAY === "1";
}

/** Store methods replay drives. Matches the subset `useDebateStream` uses. */
export interface ReplaySink {
  startRun: (runId: string) => void;
  addTurn: (turn: Turn) => void;
  setVerdict: (verdict: Verdict) => void;
  setError: (error: string) => void;
}

export interface ReplayOptions {
  /** Pause before each turn, ms. Stands in for model latency. */
  turnDelay?: number;
  /** Pause before the verdict, ms. The judge reads everything, so it is slower. */
  verdictDelay?: number;
  /** Aborts an in-flight replay. */
  signal?: AbortSignal;
  /** Injectable for tests, which run replay with no real waiting. */
  sleep?: (ms: number) => Promise<void>;
}

const defaultSleep = (ms: number) =>
  new Promise<void>((resolve) => window.setTimeout(resolve, ms));

/**
 * Applies one fixture event to the store.
 *
 * Shared by auto-play and by stepping, so the two cannot diverge: a bug in
 * how a turn reaches the store would otherwise be reproducible in one mode
 * and not the other.
 *
 * Returns false for an event that ends the run (`error`), true otherwise.
 * `done` is ignored, as the stream handler ignores it — the verdict is what
 * moves the courtroom to `adjourned`.
 */
export function applyEvent(sink: ReplaySink, { event, data }: ReplayEvent): boolean {
  switch (event) {
    case "start":
      sink.startRun((data as { run_id: string }).run_id);
      return true;
    case "turn":
      sink.addTurn(data as Turn);
      return true;
    case "verdict":
      sink.setVerdict(data as Verdict);
      return true;
    case "error":
      sink.setError((data as { error: string }).error);
      return false;
    case "done":
      return true;
  }
}

/** How long to pause before an event when playing automatically. */
export function delayFor(
  event: ReplayEvent["event"],
  { turnDelay = 1600, verdictDelay = 2400 }: Pick<ReplayOptions, "turnDelay" | "verdictDelay">,
): number {
  if (event === "turn") return turnDelay;
  if (event === "verdict") return verdictDelay;
  return 0;
}

/**
 * Pushes the fixture's events into the store in order.
 *
 * Deliberately ignores `done`, as the stream handler does — the verdict is what
 * moves the courtroom to `adjourned`.
 */
export async function replayDebate(
  sink: ReplaySink,
  options: ReplayOptions = {},
): Promise<void> {
  const { signal, sleep = defaultSleep } = options;

  for (const replayEvent of replayEvents) {
    if (signal?.aborted) return;

    const pause = delayFor(replayEvent.event, options);
    if (pause > 0) {
      await sleep(pause);
      if (signal?.aborted) return;
    }

    if (!applyEvent(sink, replayEvent)) return;
  }
}
