import { useCallback, useRef } from "react";

import { api } from "@/api/client";
import { useCourtStore } from "@/store/courtStore";
import type { DebateConfig, Objection, Turn, Verdict } from "@/types";

/**
 * Drives a debate over SSE.
 *
 * The endpoint is a POST, so `EventSource` cannot be used — it only issues GETs.
 * This reads the response body as a stream and parses SSE frames by hand, which
 * also lets the caller abort a run cleanly.
 *
 * Events are turn-level, not token-level: a four-model debate runs for minutes
 * and what matters visually is "the doctrinal attacker raised three objections",
 * not characters trickling out of a 12B model.
 */
export function useDebateStream() {
  const abortRef = useRef<AbortController | null>(null);

  const { startRun, addTurn, setVerdict, setError, showFlourish } =
    useCourtStore();

  const stop = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  const start = useCallback(
    async (config: DebateConfig) => {
      stop();
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const response = await fetch(api.streamUrl(), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: api.streamBody(config),
          signal: controller.signal,
        });

        if (!response.ok || !response.body) {
          throw new Error(`Stream failed with status ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // SSE frames are separated by a blank line.
          const frames = buffer.split("\n\n");
          buffer = frames.pop() ?? "";

          for (const frame of frames) {
            const event = parseFrame(frame);
            if (!event) continue;

            switch (event.name) {
              case "start":
                startRun(JSON.parse(event.data).run_id as string);
                break;

              case "turn": {
                const turn = JSON.parse(event.data) as Turn;
                addTurn(turn);
                // An attacker's first objection gets the OBJECTION! flourish.
                if (turn.objections.length > 0) {
                  flourishFor(turn.objections[0], showFlourish);
                }
                break;
              }

              case "verdict":
                setVerdict(JSON.parse(event.data) as Verdict);
                break;

              case "error":
                setError(JSON.parse(event.data).error as string);
                break;

              case "done":
                break;
            }
          }
        }
      } catch (err) {
        // An aborted run is a user action, not a failure.
        if ((err as Error).name !== "AbortError") {
          setError((err as Error).message);
        }
      } finally {
        abortRef.current = null;
      }
    },
    [addTurn, setError, setVerdict, showFlourish, startRun, stop],
  );

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

interface Frame {
  name: string;
  data: string;
}

/** Parses one SSE frame into its event name and data payload. */
function parseFrame(raw: string): Frame | null {
  let name = "message";
  const dataLines: string[] = [];

  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) {
      name = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trim());
    }
  }

  if (dataLines.length === 0) return null;
  return { name, data: dataLines.join("\n") };
}
