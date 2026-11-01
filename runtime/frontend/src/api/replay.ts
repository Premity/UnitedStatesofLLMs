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
 * Pushes the fixture's events into the store in order.
 *
 * Deliberately ignores `done`, as the stream handler does — the verdict is what
 * moves the courtroom to `adjourned`.
 */
export async function replayDebate(
  sink: ReplaySink,
  options: ReplayOptions = {},
): Promise<void> {
  const {
    turnDelay = 1600,
    verdictDelay = 2400,
    signal,
    sleep = defaultSleep,
  } = options;

  for (const { event, data } of replayEvents) {
    if (signal?.aborted) return;

    switch (event) {
      case "start":
        sink.startRun((data as { run_id: string }).run_id);
        break;

      case "turn":
        await sleep(turnDelay);
        if (signal?.aborted) return;
        sink.addTurn(data as Turn);
        break;

      case "verdict":
        await sleep(verdictDelay);
        if (signal?.aborted) return;
        sink.setVerdict(data as Verdict);
        break;

      case "error":
        sink.setError((data as { error: string }).error);
        return;

      case "done":
        break;
    }
  }
}
