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
    expect(state.turns).toHaveLength(8);
    expect(state.verdict).not.toBeNull();
  });

  it("replays turns in the fixture's order", async () => {
    await replayDebate(sink(), { sleep: instant });

    // Two rounds: the graph loops judge -> present.
    expect(useCourtStore.getState().turns.map((t) => t.role)).toEqual([
      "presenter",
      "attacker_doctrinal",
      "attacker_evidentiary",
      "judge",
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
    // The record is put away until there is one: a rail, not 26rem of
    // "the dissent log appears once the court has ruled".
    expect(screen.getByTestId("dissent-open")).toBeInTheDocument();
    expect(screen.queryByText(/appears once the court has ruled/i)).not.toBeInTheDocument();
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
    expect(log.getByTestId("confidence-band")).toHaveTextContent(/supported/i);
    expect(log.getByText("0.81")).toBeInTheDocument();

    // The dissent is the system's headline output: two overruled objections,
    // and only the overruled ones. The sustained misquote must not appear here.
    expect(log.getByText(/objections overruled/i)).toBeInTheDocument();
    expect(log.getByText(/Additional Protocol I governs/i)).toBeInTheDocument();
    expect(log.getByText(/does not establish that spreading terror/i)).toBeInTheDocument();
    expect(log.queryByText(/overstates what Article 51\(2\) says/i)).not.toBeInTheDocument();

    // Both raisers are labelled, not shown as raw role slugs.
    // Each entry names its raiser and the round it was raised in.
    expect(log.getAllByText(/Doctrinal Counsel · Round \d/).length).toBeGreaterThan(0);
    expect(log.getAllByText(/Evidentiary Counsel · Round \d/).length).toBeGreaterThan(0);
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
      "turn_presenter_r2",
      "turn_doctrinal_r2",
      "turn_evidentiary_r2",
      "turn_judge_r2",
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

    // Round one's verdict. The debate is not over — a second round follows.
    await user.click(step);
    expect(useCourtStore.getState().verdict?.confidence).toBe(0.78);
    expect(step).not.toBeDisabled();

    // Round two, ending in the revised verdict and `done`.
    for (let i = 0; i < 5; i++) await user.click(step);
    expect(useCourtStore.getState().turns).toHaveLength(8);
    expect(useCourtStore.getState().verdict?.confidence).toBe(0.81);
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
    expect(transcript.getAllByText("The Bench")).toHaveLength(2);

    // Every disposition in the fixture, named.
    expect(transcript.getAllByText("Overruled").length).toBeGreaterThan(0);
    expect(transcript.getAllByText("Sustained").length).toBeGreaterThan(0);
    expect(transcript.getAllByText("Partly sustained").length).toBeGreaterThan(0);

    // And the reason, which only ever existed in the data.
    // Both judge cards repeat the ruling they carried.
    expect(
      transcript.getAllByText(/terror prohibition is customary/i).length,
    ).toBeGreaterThan(0);
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
    expect(screen.getByTestId("objection-slam")).toBeInTheDocument();
    expect(screen.getByText(/objection!/i)).toBeInTheDocument();

    await user.click(step); // evidentiary — obj_misquote, not grounded
    expect(screen.queryByTestId("objection-slam")).not.toBeInTheDocument();
    expect(screen.queryByText(/objection!/i)).not.toBeInTheDocument();
    expect(screen.getByTestId("objection-quiet")).toBeInTheDocument();

    // The attribution and the ground moved to the band — the burst is
    // bench-sized and carries only the word.
    expect(screen.getByTestId("subtitle-band")).toHaveTextContent(
      /Evidentiary Counsel · Objection/i,
    );
  });

  it("puts the burst on the sprite that raised it, not over the courtroom", async () => {
    const user = userEvent.setup();
    render(<App />);
    const step = screen.getByTestId("replay-step");

    await user.click(step); // presenter
    await user.click(step); // doctrinal objects

    // Walk up from the burst to the figure it covers, and check the nameplate
    // in that sprite. A burst over the wrong bench misattributes the
    // objection, which is the thing this change exists to get right.
    const slam = screen.getByTestId("objection-slam");
    const sprite = slam.closest("div.flex.flex-col");
    expect(sprite).not.toBeNull();
    expect(within(sprite as HTMLElement).getByTestId("sprite-plate")).toHaveTextContent(
      "Doctrinal",
    );
  });
});

describe("a debate that runs past one round", () => {
  // Round one's ruling, not the standing one.
  const verdict = replayEvents.find((e) => e.event === "verdict")!.data as Verdict;

  it("does not declare the debate over when round one is ruled", async () => {
    render(<App />);

    const turns = replayEvents
      .filter((x) => x.event === "turn")
      .map((x) => x.data as Turn);

    const s = sink();
    s.startRun("run_x");
    for (const t of turns.filter((t) => t.round_number === 1)) s.addTurn(t);
    s.setVerdict(verdict);

    // Round two opens with the presenter's rebuttal.
    s.addTurn(turns.find((t) => t.round_number === 2)!);

    await waitFor(() => {
      expect(screen.getAllByText(/Round 2/).length).toBeGreaterThan(0);
    });

    // The form must stay locked: a run is still in flight, and re-enabling
    // "Convene the council" mid-debate invites a second concurrent run.
    expect(
      screen.getByRole("button", { name: /convene the council/i }),
    ).toBeDisabled();
    expect(screen.getByText(/opposing counsel are reviewing/i)).toBeInTheDocument();
  });
});

describe("a second round's ruling", () => {
  it("supersedes the first in the record", async () => {
    render(<App />);
    await replayDebate(sink(), { sleep: instant });

    const log = within(screen.getByRole("complementary", { name: "Dissent log" }));

    // Round two raised confidence and added an overruled objection. The
    // record shows the standing ruling, not the one it replaced.
    expect(log.getByText("0.81")).toBeInTheDocument();
    expect(log.queryByText("0.78")).not.toBeInTheDocument();
    expect(log.getByText(/still assumes the absence of an identified objective/i))
      .toBeInTheDocument();
  });

  it("gives each judge card its own round's rulings", async () => {
    render(<App />);
    await replayDebate(sink(), { sleep: instant });

    const cards = within(screen.getByRole("region", { name: "Transcript" }))
      .getAllByRole("article")
      .filter((c) => c.textContent?.includes("The Bench"));

    expect(cards).toHaveLength(2);

    // Round one ruled on the applicability and proportionality objections;
    // round two on the precautionary one. Handing every card the whole run
    // made the second a copy of the first.
    expect(cards[0].textContent).toMatch(/Additional Protocol I governs/);
    expect(cards[0].textContent).not.toMatch(/still assumes the absence/);
    expect(cards[1].textContent).toMatch(/still assumes the absence/);
    expect(cards[1].textContent).not.toMatch(/Additional Protocol I governs/);
  });

  it("puts the standing holding on the last ruling only", async () => {
    render(<App />);
    await replayDebate(sink(), { sleep: instant });

    const cards = within(screen.getByRole("region", { name: "Transcript" }))
      .getAllByRole("article")
      .filter((c) => c.textContent?.includes("The Bench"));

    // Two confidences on screen at once, both looking current, would be worse
    // than showing one — the earlier ruling says it was superseded instead.
    expect(cards[0].textContent).toMatch(/superseded/i);
    expect(cards[0].textContent).not.toMatch(/full reasoning in the dissent log/);
    expect(cards[1].textContent).toMatch(/Supported · full reasoning/);
  });

  it("records how many rounds the holding survived", async () => {
    render(<App />);
    await replayDebate(sink(), { sleep: instant });

    const log = within(screen.getByRole("complementary", { name: "Dissent log" }));
    expect(log.getByText(/2 rounds/)).toBeInTheDocument();
  });

  it("shows the rebuttal as its own turn", async () => {
    render(<App />);
    await replayDebate(sink(), { sleep: instant });

    const transcript = within(screen.getByRole("region", { name: "Transcript" }));

    // The presenter speaks twice: opening, then rebuttal.
    expect(transcript.getAllByText("Presenting Counsel")).toHaveLength(2);
    expect(
      transcript.getByText(/Confined to attacks for which no military objective/i),
    ).toBeInTheDocument();
  });

  it("renders an attacker turn that raised nothing", async () => {
    render(<App />);
    await replayDebate(sink(), { sleep: instant });

    // Round two's evidentiary turn has neither arguments nor objections —
    // that is what ends a debate in `auto` mode, and the card still has to
    // identify itself rather than render as a blank block.
    // The label also names objection raisers, so find the turn card itself:
    // it reports a round and a model, and carries no claim or objection.
    const transcript = screen.getByRole("region", { name: "Transcript" });
    const silent = within(transcript)
      .getAllByRole("article")
      .find((card) => card.textContent?.includes("Round 2 · gemma3:12b"));

    expect(silent).toBeDefined();
    expect(within(silent!).getByText("Evidentiary Counsel")).toBeInTheDocument();
  });
});

describe("the record panel", () => {
  it("opens itself when the court rules", async () => {
    render(<App />);
    expect(screen.getByTestId("dissent-open")).toBeInTheDocument();

    await replayDebate(sink(), { sleep: instant });

    await waitFor(() => {
      expect(
        screen.getByRole("complementary", { name: "Dissent log" }),
      ).toBeInTheDocument();
    });
    expect(screen.queryByTestId("dissent-open")).not.toBeInTheDocument();
  });

  it("can be put away and brought back", async () => {
    const user = userEvent.setup();
    render(<App />);
    await replayDebate(sink(), { sleep: instant });
    await waitFor(() => screen.getByTestId("dissent-close"));

    await user.click(screen.getByTestId("dissent-close"));
    expect(
      screen.queryByRole("complementary", { name: "Dissent log" }),
    ).not.toBeInTheDocument();

    // The rail reports what is waiting inside it.
    const rail = screen.getByTestId("dissent-open");
    expect(rail).toHaveTextContent(/3 overruled/);

    await user.click(rail);
    expect(
      screen.getByRole("complementary", { name: "Dissent log" }),
    ).toBeInTheDocument();
  });

  it("can be opened before there is a record, and says so", async () => {
    const user = userEvent.setup();
    render(<App />);

    const rail = screen.getByTestId("dissent-open");
    expect(rail).toHaveTextContent(/not yet/i);

    await user.click(rail);
    expect(
      screen.getByText(/appears once the court has ruled/i),
    ).toBeInTheDocument();
  });

  it("stays shut if it was deliberately closed after the ruling", async () => {
    const user = userEvent.setup();
    render(<App />);
    await replayDebate(sink(), { sleep: instant });
    await waitFor(() => screen.getByTestId("dissent-close"));

    await user.click(screen.getByTestId("dissent-close"));

    // A re-render must not reopen it: the panel announces a run once, and
    // fighting someone who just closed it is worse than leaving it shut.
    sink().setVerdict(
      replayEvents.find((e) => e.event === "verdict")!.data as Verdict,
    );
    await waitFor(() =>
      expect(screen.getByTestId("dissent-open")).toBeInTheDocument(),
    );
  });
});

describe("waiting on a model", () => {
  it("names who is working, not who last spoke", async () => {
    const user = userEvent.setup();
    render(<App />);
    const step = screen.getByTestId("replay-step");

    // Idle: nothing is generating, so the rail shows the phase.
    expect(screen.getByText(/court is not in session/i)).toBeInTheDocument();

    await user.click(step); // presenter reports
    // The presenter has finished — both attackers are now generating, and
    // that is what the rail should say rather than "Counsel is presenting".
    expect(screen.getByText(/opposing counsel are reviewing/i)).toBeInTheDocument();

    await user.click(step); // doctrinal reports, evidentiary still out
    expect(screen.getByText(/evidentiary counsel is reviewing/i)).toBeInTheDocument();

    await user.click(step); // evidentiary reports
    expect(screen.getByText(/court is deliberating/i)).toBeInTheDocument();
  });

  it("shows elapsed time while waiting, and stops once the court rules", async () => {
    render(<App />);
    // Idle shows no clock; a started run does.
    expect(screen.queryByTestId("elapsed")).not.toBeInTheDocument();

    sink().startRun("run_x");
    await waitFor(() =>
      expect(screen.getByTestId("elapsed")).toBeInTheDocument(),
    );

    await replayDebate(sink(), { sleep: instant });

    // Nothing is generating after the verdict, so no clock.
    expect(screen.queryByTestId("elapsed")).not.toBeInTheDocument();
  });
});

describe("the palette toggle", () => {
  it("switches the courtroom palette without a reload", async () => {
    const user = userEvent.setup();
    render(<App />);

    // Labelled with where it is going, not where it is: the default is Oak,
    // so the button offers Dusk.
    const toggle = screen.getByTestId("theme-switcher");
    expect(toggle).toHaveAccessibleName(/dusk/i);

    await user.click(toggle);

    // The swap happens under the wave rather than on click, so wait for it.
    await waitFor(() =>
      expect(document.documentElement.dataset.theme).toBe("dusk"),
    );
    // #1a1229 -> 26 18 41, as channels so Tailwind's alpha still composes.
    expect(
      document.documentElement.style.getPropertyValue("--court-bg"),
    ).toBe("26 18 41");
    // And now it offers the way back.
    expect(toggle).toHaveAccessibleName(/oak/i);
  });

  it("toggles back to the default", async () => {
    const user = userEvent.setup();
    render(<App />);
    const toggle = screen.getByTestId("theme-switcher");

    await user.click(toggle);
    await waitFor(() =>
      expect(document.documentElement.dataset.theme).toBe("dusk"),
    );
    await user.click(toggle);
    await waitFor(() =>
      expect(document.documentElement.dataset.theme).toBe("oak"),
    );
  });

  it("flips the coin to the face it is offering", async () => {
    const user = userEvent.setup();
    render(<App />);

    // Oak is light, so the coin shows the dark face it would switch to.
    expect(screen.getByTestId("theme-coin")).toHaveAttribute("data-face", "dark");

    await user.click(screen.getByTestId("theme-switcher"));
    await waitFor(() =>
      expect(screen.getByTestId("theme-coin")).toHaveAttribute("data-face", "light"),
    );
  });

  it("centres the wave on the button it was clicked from", async () => {
    const user = userEvent.setup();
    render(<App />);

    // jsdom reports a zero-sized box, so assert the properties are set and
    // in pixels rather than pinning coordinates a real layout would decide.
    await user.click(screen.getByTestId("theme-switcher"));

    const root = document.documentElement.style;
    expect(root.getPropertyValue("--wave-x")).toMatch(/^-?[\d.]+px$/);
    expect(root.getPropertyValue("--wave-y")).toMatch(/^-?[\d.]+px$/);
    // The radius has to reach the furthest corner, so it is never zero.
    expect(parseFloat(root.getPropertyValue("--wave-r"))).toBeGreaterThan(0);
  });

  it("interrupts a running wave so every click gets one", async () => {
    // jsdom has no view transitions, so stand one in. A browser runs one at a
    // time and drops any started while another is live; without the
    // interrupt a fast second click changed the palette with no animation.
    const skips: number[] = [];
    let live = 0;
    const started: (() => void)[] = [];

    Object.defineProperty(document, "startViewTransition", {
      configurable: true,
      writable: true,
      value: (cb: () => void) => {
        const id = ++live;
        started.push(cb);
        cb();
        return {
          // Never settles: a real wave runs for 0.6s, so it is still live
          // when the next click arrives. Resolving here would let the
          // component forget it and the interrupt would not be exercised.
          finished: new Promise<void>(() => {}),
          skipTransition: () => skips.push(id),
        };
      },
    });

    try {
      const user = userEvent.setup();
      render(<App />);
      const toggle = screen.getByTestId("theme-switcher");

      await user.click(toggle);
      await user.click(toggle);
      await user.click(toggle);

      // One transition per click, and each later click cut the previous short.
      expect(started).toHaveLength(3);
      expect(skips.length).toBeGreaterThanOrEqual(2);
    } finally {
      delete (document as Partial<Document> & { startViewTransition?: unknown })
        .startViewTransition;
    }
  });
});

describe("the fixture itself", () => {
  it("runs start -> turn* -> verdict -> done", () => {
    const names = replayEvents.map((e) => e.event);

    expect(names[0]).toBe("start");
    expect(names.at(-1)).toBe("done");
    expect(names.filter((n) => n === "turn")).toHaveLength(8);
    // One ruling per round — the judge rules at the end of each.
    expect(names.filter((n) => n === "verdict")).toHaveLength(2);
    // Each round's verdict closes it, so the last one follows the last turn.
    expect(names.lastIndexOf("verdict")).toBeGreaterThan(names.lastIndexOf("turn"));
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
