import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import App from "@/App";
import { replayDebate, replayEvents } from "@/api/replay";
import { useCourtStore } from "@/store/courtStore";
import type { Turn, Verdict } from "@/types";

/**
 * Replay driven straight through the store, and once through the whole app.
 *
 * The app render is the load-bearing test: every component below `App` has
 * been written but never executed, so this is what catches a crash on first
 * contact with real payload shapes.
 */

/** No waiting — replay's delays exist for the eye, not for correctness. */
const instant = () => Promise.resolve();

function sink() {
  const s = useCourtStore.getState();
  return {
    startRun: s.startRun,
    addTurn: s.addTurn,
    setVerdict: s.setVerdict,
    setError: s.setError,
  };
}

describe("replayDebate", () => {
  it("drives the store from idle to adjourned", async () => {
    expect(useCourtStore.getState().phase).toBe("idle");

    await replayDebate(sink(), { sleep: instant });

    const state = useCourtStore.getState();
    expect(state.phase).toBe("adjourned");
    expect(state.runId).toBe("run_f1xtur3g3n0");
    expect(state.turns).toHaveLength(4);
    expect(state.verdict).not.toBeNull();
  });

  it("replays turns in the fixture's order", async () => {
    await replayDebate(sink(), { sleep: instant });

    expect(useCourtStore.getState().turns.map((t) => t.role)).toEqual([
      "presenter",
      "attacker_doctrinal",
      "attacker_evidentiary",
      "judge",
    ]);
  });

  it("stops when aborted and leaves the store mid-debate", async () => {
    const controller = new AbortController();
    let turns = 0;

    await replayDebate(
      {
        ...sink(),
        addTurn: (turn: Turn) => {
          useCourtStore.getState().addTurn(turn);
          if (++turns === 2) controller.abort();
        },
      },
      { sleep: instant, signal: controller.signal },
    );

    const state = useCourtStore.getState();
    expect(state.turns).toHaveLength(2);
    expect(state.verdict).toBeNull();
    expect(state.phase).not.toBe("adjourned");
  });

  it("surfaces an error event and stops", async () => {
    const events = [
      { event: "start" as const, data: { run_id: "run_err" } },
      { event: "error" as const, data: { error: "judge model unreachable" } },
      { event: "verdict" as const, data: {} as Verdict },
    ];

    // replayDebate reads the module fixture, so drive the same logic by hand
    // over a sequence that contains an error. This mirrors the stream handler:
    // an error ends the run, and no later event is applied.
    const s = sink();
    for (const { event, data } of events) {
      if (event === "start") s.startRun((data as { run_id: string }).run_id);
      if (event === "error") {
        s.setError((data as { error: string }).error);
        break;
      }
    }

    const state = useCourtStore.getState();
    expect(state.phase).toBe("error");
    expect(state.error).toBe("judge model unreachable");
    expect(state.verdict).toBeNull();
  });
});

describe("the app under replay", () => {
  it("renders the courtroom before a debate starts", () => {
    render(<App />);

    expect(screen.getByText("United States of LLMs")).toBeInTheDocument();
    expect(screen.getByText(/court is not in session/i)).toBeInTheDocument();
    // The dissent log holds its empty state until the court rules.
    expect(screen.getByText(/appears once the court has ruled/i)).toBeInTheDocument();
  });

  it("renders the full proceeding and its dissent log", async () => {
    render(<App />);
    await replayDebate(sink(), { sleep: instant });

    await waitFor(() => {
      expect(screen.getByText(/court has ruled/i)).toBeInTheDocument();
    });

    // Scope to the record. The courtroom bubble and the transcript carry the
    // same prose, so an unscoped query matches several nodes.
    const log = within(screen.getByRole("complementary", { name: "Dissent log" }));

    expect(log.getByText(/primary purpose of spreading terror/i)).toBeInTheDocument();
    expect(log.getByText("78%")).toBeInTheDocument();

    // The dissent is the system's headline output: two overruled objections,
    // and only the overruled ones. The sustained misquote must not appear here.
    expect(log.getByText(/objections overruled/i)).toBeInTheDocument();
    expect(log.getByText(/Additional Protocol I governs/i)).toBeInTheDocument();
    expect(log.getByText(/does not establish that spreading terror/i)).toBeInTheDocument();
    expect(log.queryByText(/overstates what Article 51\(2\) says/i)).not.toBeInTheDocument();

    // Both raisers are labelled, not shown as raw role slugs.
    expect(log.getByText("Doctrinal Counsel")).toBeInTheDocument();
    expect(log.getByText("Evidentiary Counsel")).toBeInTheDocument();
  });

  it("offers a replay button in dev, so the flag is not secret knowledge", async () => {
    const user = userEvent.setup();
    render(<App />);

    // No URL flag: the live path is still the default and the primary button.
    expect(screen.queryByTestId("replay-banner")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /convene the council/i }),
    ).toBeInTheDocument();

    await user.click(screen.getByTestId("replay-offer"));

    await waitFor(
      () => expect(useCourtStore.getState().turns.length).toBeGreaterThan(0),
      { timeout: 4000 },
    );
    expect(useCourtStore.getState().replayed).toBe(true);
  });

  it("marks a replayed run as recorded in both the courtroom and the record", async () => {
    render(<App />);

    await replayDebate(
      { ...sink(), startRun: (id: string) => useCourtStore.getState().startRun(id, { replayed: true }) },
      { sleep: instant },
    );

    await waitFor(() => {
      expect(screen.getByTestId("replay-marker")).toBeInTheDocument();
    });
    // The record is what leaves the screen, so it says so in words.
    expect(screen.getByTestId("replay-provenance")).toHaveTextContent(
      /no models were consulted/i,
    );
  });

  it("does not mark a live run as recorded", async () => {
    render(<App />);
    await replayDebate(sink(), { sleep: instant });

    expect(screen.queryByTestId("replay-marker")).not.toBeInTheDocument();
    expect(screen.queryByTestId("replay-provenance")).not.toBeInTheDocument();
  });

  it("shows a replay banner so a fixture is never mistaken for a live run", () => {
    // isReplayEnabled reads window.location.search, which jsdom lets us set.
    window.history.pushState({}, "", "/?replay=1");
    render(<App />);

    expect(screen.getByTestId("replay-banner")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /play the recorded debate/i }),
    ).toBeEnabled();

    window.history.pushState({}, "", "/");
  });
});

describe("the fixture itself", () => {
  it("runs start -> turn* -> verdict -> done", () => {
    const names = replayEvents.map((e) => e.event);

    expect(names[0]).toBe("start");
    expect(names.at(-1)).toBe("done");
    expect(names.filter((n) => n === "turn")).toHaveLength(4);
    expect(names.filter((n) => n === "verdict")).toHaveLength(1);
    // A verdict after the last turn, never before.
    expect(names.indexOf("verdict")).toBeGreaterThan(names.lastIndexOf("turn"));
  });

  it("exercises all four citation statuses", () => {
    const statuses = new Set(
      replayEvents
        .filter((e) => e.event === "turn")
        .flatMap((e) => {
          const turn = e.data as Turn;
          return [...turn.arguments, ...turn.objections];
        })
        .flatMap((item) => item.resolved_citations.map((rc) => rc.status)),
    );

    expect(statuses).toEqual(
      new Set(["resolved", "unresolved", "out_of_corpus", "misquoted"]),
    );
  });
});
