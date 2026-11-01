import { useCallback, useRef } from "react";

import { replayDebate } from "@/api/replay";
import { useCourtStore } from "@/store/courtStore";
import type { Objection, Turn } from "@/types";

/**
 * Drives a debate from the fixture instead of the network.
 *
 * Mirrors `useDebateStream`'s surface — `{ start, stop }` — so `QuestionForm`
 * can swap one for the other without knowing which it holds. The flourish
 * behaviour is duplicated rather than shared because it belongs to how events
 * are presented, and keeping the stream hook free of replay imports means the
 * production path cannot accidentally depend on the fixture.
 */
export function useReplay() {
  const abortRef = useRef<AbortController | null>(null);

  const { startRun, addTurn, setVerdict, setError, showFlourish } =
    useCourtStore();

  const stop = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  const start = useCallback(async () => {
    stop();
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await replayDebate(
        {
          startRun: (runId: string) => startRun(runId, { replayed: true }),
          setVerdict,
          setError,
          addTurn: (turn: Turn) => {
            addTurn(turn);
            if (turn.objections.length > 0) {
              flourishFor(turn.objections[0], showFlourish);
            }
          },
        },
        { signal: controller.signal },
      );
    } finally {
      abortRef.current = null;
    }
  }, [addTurn, setError, setVerdict, showFlourish, startRun, stop]);

  return { start, stop };
}

/** Shows the objection flourish, then clears it after the animation. */
function flourishFor(
  objection: Objection,
  show: (o: Objection | null) => void,
): void {
  show(objection);
  window.setTimeout(() => show(null), 1400);
}
