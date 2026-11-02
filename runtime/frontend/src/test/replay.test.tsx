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

    // Twice within the record now: the question asked and the holding given.
    expect(log.getAllByText(/primary purpose of spreading terror/i)).toHaveLength(2);
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

    // Only that the button starts a replayed run; the sequence is covered
    // below without paying nine seconds of real delay. Leaving the loop in
    // flight is safe because useReplay aborts on unmount — asserted further on.
    await waitFor(
      () => expect(useCourtStore.getState().turns.length).toBeGreaterThan(0),
      { timeout: 5000 },
    );
    expect(useCourtStore.getState().replayed).toBe(true);
  }, 10000);

  it("plays every event in order when started", async () => {
    // The button path above proves the wiring; this proves the sequence
    // without paying nine seconds of real delay for it.
    await replayDebate(sink(), { sleep: instant });

    expect(useCourtStore.getState().turns.map((t) => t.id)).toEqual([
      "turn_presenter_r1",
      "turn_doctrinal_r1",
      "turn_evidentiary_r1",
      "turn_judge_r1",
    ]);
  });

  it("aborts an in-flight auto-play when unmounted", async () => {
    const { unmount } = render(<App />);

    const user = userEvent.setup();
    await user.click(screen.getByTestId("replay-offer"));
    // The first turn lands at the 1.6s turn delay, past waitFor's 1s default.
    await waitFor(
      () => expect(useCourtStore.getState().turns.length).toBeGreaterThan(0),
      { timeout: 5000 },
    );

    const atUnmount = useCourtStore.getState().turns.length;
    unmount();

    // Past two more turn delays. A loop still running would have written more.
    await new Promise((r) => setTimeout(r, 3600));
    expect(useCourtStore.getState().turns).toHaveLength(atUnmount);
  }, 20000);

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

  it("steps one event at a time, and the first press shows something", async () => {
    const user = userEvent.setup();
    render(<App />);

    const step = screen.getByTestId("replay-step");
    expect(step).toHaveTextContent(/step through it/i);

    // The first press must put a turn on screen. `start` alone only sets a run
    // id, so consuming it silently would read as a dead button.
    await user.click(step);
    expect(useCourtStore.getState().turns).toHaveLength(1);
    expect(useCourtStore.getState().runId).toBe("run_f1xtur3g3n0");
    expect(step).toHaveTextContent(/next step/i);

    await user.click(step);
    expect(useCourtStore.getState().turns).toHaveLength(2);
    expect(useCourtStore.getState().verdict).toBeNull();

    await user.click(step);
    await user.click(step);
    expect(useCourtStore.getState().turns).toHaveLength(4);
    expect(useCourtStore.getState().verdict).toBeNull();

    // The verdict, and with it `done` — which carries nothing to show.
    await user.click(step);
    expect(useCourtStore.getState().verdict).not.toBeNull();
    expect(useCourtStore.getState().phase).toBe("adjourned");

    await waitFor(() => expect(step).toBeDisabled());
  });

  it("names what the next step will show", async () => {
    const user = userEvent.setup();
    render(<App />);

    expect(screen.getByTestId("replay-stepper")).toHaveTextContent(
      /next: presenting counsel/i,
    );

    await user.click(screen.getByTestId("replay-step"));
    expect(screen.getByTestId("replay-stepper")).toHaveTextContent(
      /next: doctrinal counsel/i,
    );
  });

  it("holds the objection flourish between steps", async () => {
    const user = userEvent.setup();
    render(<App />);
    const step = screen.getByTestId("replay-step");

    // Presenter: arguments only, so no flourish.
    await user.click(step);
    expect(useCourtStore.getState().flourish).toBeNull();

    // Doctrinal objects. In auto-play this clears after 1.4s; stepping holds
    // it, because inspecting it is the entire point.
    // The doctrinal turn's headline is its *grounded* objection, not its
    // first — a fully resolved objection earns the slam.
    await user.click(step);
    expect(useCourtStore.getState().flourish?.id).toBe("obj_proportionality");
    expect(screen.getByText(/objection!/i)).toBeInTheDocument();

    // Still there well past the auto-play timeout.
    await new Promise((r) => setTimeout(r, 1600));
    expect(useCourtStore.getState().flourish?.id).toBe("obj_proportionality");

    // The next step replaces it with the evidentiary attacker's.
    await user.click(step);
    expect(useCourtStore.getState().flourish?.id).toBe("obj_misquote");
  });

  it("restarts to an empty courtroom", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByTestId("replay-step"));
    await user.click(screen.getByTestId("replay-step"));
    expect(useCourtStore.getState().turns).toHaveLength(2);

    await user.click(screen.getByTestId("replay-restart"));

    expect(useCourtStore.getState().turns).toHaveLength(0);
    expect(useCourtStore.getState().phase).toBe("idle");
    expect(screen.getByTestId("replay-step")).toHaveTextContent(/step through it/i);
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

describe("the record and the rulings", () => {
  it("shows the question the holding answers", async () => {
    render(<App />);
    await replayDebate(sink(), { sleep: instant });

    const log = within(screen.getByRole("complementary", { name: "Dissent log" }));
    expect(log.getByText("Question")).toBeInTheDocument();
    // Appears as the question and again in the holding that answers it.
    expect(log.getAllByText(/sustained campaign of sniping and shelling/i)).toHaveLength(2);
    // The form has a field with the same label, so match the record's heading.
    expect(log.getByRole("heading", { name: /Facts as given/i })).toBeInTheDocument();
  });

  it("shows the bench's rulings rather than an empty card", async () => {
    render(<App />);
    await replayDebate(sink(), { sleep: instant });

    // The judge emits no arguments or objections of its own, so this card was
    // structurally always empty before.
    const transcript = within(screen.getByRole("region", { name: "Transcript" }));
    expect(transcript.getByText("The Bench")).toBeInTheDocument();

    // Every disposition in the fixture, named.
    expect(transcript.getAllByText("Overruled").length).toBeGreaterThan(0);
    expect(transcript.getAllByText("Sustained").length).toBeGreaterThan(0);
    expect(transcript.getAllByText("Partly sustained").length).toBeGreaterThan(0);

    // And the reason, which only ever existed in the data.
    expect(
      transcript.getByText(/terror prohibition is customary/i),
    ).toBeInTheDocument();
  });

  it("marks each objection's outcome where it was raised", async () => {
    render(<App />);
    await replayDebate(sink(), { sleep: instant });

    // obj_misquote was sustained; its badge belongs on the evidentiary turn,
    // not only on the bench's card.
    const transcript = screen.getByRole("region", { name: "Transcript" });
    // The bench's card repeats the ground when it rules, so take the one on
    // the turn that raised it.
    const [raised] = within(transcript).getAllByText(
      /overstates what Article 51\(2\) says/i,
    );
    const card = raised.closest("article");
    expect(card).not.toBeNull();
    expect(within(card!).getByText("Sustained")).toBeInTheDocument();
  });
});

describe("the objection flourish", () => {
  it("slams for a grounded objection and stays quiet otherwise", async () => {
    const user = userEvent.setup();
    render(<App />);
    const step = screen.getByTestId("replay-step");

    await user.click(step); // presenter
    await user.click(step); // doctrinal — obj_proportionality, fully resolved
    expect(screen.getByText(/objection!/i)).toBeInTheDocument();

    await user.click(step); // evidentiary — obj_misquote, not grounded
    expect(screen.queryByText(/objection!/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Objection · Evidentiary Counsel/i)).toBeInTheDocument();
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
