import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { applyEvent, replayDebate, replayEvents } from "@/api/replay";
import type { ReplayOptions, ReplaySink } from "@/api/replay";
import { useCourtStore } from "@/store/courtStore";
import type { Turn } from "@/types";

/**
 * Drives a debate from the fixture instead of the network.
 *
 * Two modes over the same events. Auto-play mirrors `useDebateStream`'s
 * `{ start, stop }` surface so `QuestionForm` can hold either without knowing
 * which. Stepping hands one event over per call, which is what makes the
 * courtroom inspectable — a debate that plays in nine seconds is too fast to
 * read, and the interesting states (an objection flourish, a citation chip)
 * are exactly the transient ones.
 *
 * Both modes go through `applyEvent`, so they cannot drift apart.
 *
 * The flourish behaviour is duplicated from the stream hook rather than
 * shared: keeping that hook free of any import reaching the fixture means the
 * production path cannot depend on it.
 */
export function useReplay() {
  const abortRef = useRef<AbortController | null>(null);
  const [cursor, setCursor] = useState(0);

  const { startRun, addTurn, setVerdict, setError, showFlourish, reset } =
    useCourtStore();

  /**
   * `hold` keeps the objection flourish on screen instead of clearing it after
   * the animation. Stepping exists to inspect transient states, and the
   * flourish is the most transient one there is.
   */
  const makeSink = useCallback(
    ({ hold }: { hold: boolean }): ReplaySink => ({
      startRun: (runId: string) => startRun(runId, { replayed: true }),
      setVerdict,
      setError,
      addTurn: (turn: Turn) => {
        addTurn(turn);
        if (turn.objections.length > 0) {
          showFlourish(turn.objections[0]);
          if (!hold) {
            window.setTimeout(() => showFlourish(null), 1400);
          }
        }
      },
    }),
    [addTurn, setError, setVerdict, showFlourish, startRun],
  );

  const autoSink = useMemo(() => makeSink({ hold: false }), [makeSink]);
  const stepSink = useMemo(() => makeSink({ hold: true }), [makeSink]);

  const stop = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  // Auto-play runs for about nine seconds. Without this, navigating away mid
  // debate leaves the loop writing turns into the store behind a courtroom
  // nobody is looking at.
  useEffect(() => () => abortRef.current?.abort(), []);

  const start = useCallback(
    async (options: ReplayOptions = {}) => {
      stop();
      reset();
      setCursor(replayEvents.length);

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        await replayDebate(autoSink, { ...options, signal: controller.signal });
      } finally {
        abortRef.current = null;
      }
    },
    [autoSink, reset, stop],
  );

  /**
   * Applies the next event and advances.
   *
   * `start` is consumed together with the first turn: on its own it only sets
   * a run id, so a first press that appeared to do nothing would read as a
   * broken button.
   */
  const step = useCallback(() => {
    stop();
    // Clear a flourish held from the previous step before showing the next.
    showFlourish(null);

    let index = cursor;
    if (index === 0) {
      applyEvent(stepSink, replayEvents[0]);
      index = 1;
    }
    if (index >= replayEvents.length) return;

    // `done` carries nothing to show, so take it with whatever precedes it.
    let next = index;
    while (next < replayEvents.length) {
      const consumed = applyEvent(stepSink, replayEvents[next]);
      next += 1;
      if (!consumed) break;
      if (replayEvents[next]?.event !== "done") break;
    }

    setCursor(next);
  }, [cursor, showFlourish, stepSink, stop]);

  const restart = useCallback(() => {
    stop();
    reset();
    setCursor(0);
  }, [reset, stop]);

  /** Events applied so far, and the total — for a "3 / 6" readout. */
  const progress = { applied: cursor, total: replayEvents.length };

  /** What the next press will show, for labelling the button. */
  const nextLabel = useMemo(() => {
    const event = replayEvents[cursor === 0 ? 1 : cursor];
    if (!event) return null;
    if (event.event === "turn") return roleLabel((event.data as Turn).role);
    if (event.event === "verdict") return "the verdict";
    return null;
  }, [cursor]);

  return {
    start,
    stop,
    step,
    restart,
    progress,
    nextLabel,
    finished: cursor >= replayEvents.length,
  };
}

const ROLE_LABEL: Record<string, string> = {
  presenter: "presenting counsel",
  attacker_doctrinal: "doctrinal counsel",
  attacker_evidentiary: "evidentiary counsel",
  judge: "the bench",
  retriever: "the clerk",
};

function roleLabel(role: string): string {
  return ROLE_LABEL[role] ?? role;
}
