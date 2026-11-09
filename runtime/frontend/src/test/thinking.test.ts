import { describe, expect, it } from "vitest";

import { replayEvents } from "@/api/replay";
import { useCourtStore } from "@/store/courtStore";
import type { Role, Turn, Verdict } from "@/types";

/**
 * Who the courtroom believes is working.
 *
 * This used to be inferred: the stream carried only completed turns, so the
 * store held a copy of the graph's shape and worked out who came next --
 * including reproducing the judge's fan-in by hand. The graph now reports its
 * own task starts as `role_started`, so these tests cover *recording* an
 * announcement rather than deducing one.
 *
 * What is still worth pinning is everything around the announcement: a role
 * clears when its turn lands, the clock measures one wait rather than
 * restarting per role, and an error or a verdict stops the spinner. Those are
 * the failures that make a courtroom look frozen or point at the wrong bench.
 */

const allTurns = replayEvents
  .filter((e) => e.event === "turn")
  .map((e) => e.data as Turn);

/** Round one on its own — these tests walk a round's hand-offs in order. */
const turns = allTurns.filter((t) => t.round_number === 1);

const verdict = replayEvents.find((e) => e.event === "verdict")?.data as Verdict;

const store = () => useCourtStore.getState();

/** Announce a role, as the server's `role_started` event does. */
const announce = (...roles: Role[]) => {
  for (const role of roles) store().roleStarted(role);
};

describe("recording who is thinking", () => {
  it("waits on nobody until the graph says so", () => {
    store().startRun("run_x");

    // Deliberately empty. The clerk used to be seeded here, which claimed a
    // role was working before the graph had reported it -- and in replay
    // showed a bench the fixture never announced.
    expect(store().pendingRoles).toEqual([]);
    expect(store().pendingSince).toBeNull();
  });

  it("waits on the clerk once the retrieve node begins", () => {
    store().startRun("run_x");
    announce("retriever");

    expect(store().pendingRoles).toEqual(["retriever"]);
    expect(store().pendingSince).not.toBeNull();
  });

  it("holds both attackers at once, because they run concurrently", () => {
    store().startRun("run_x");
    announce("attacker_doctrinal", "attacker_evidentiary");

    expect(store().pendingRoles).toEqual([
      "attacker_doctrinal",
      "attacker_evidentiary",
    ]);
  });

  it("keeps the slower attacker pending when the faster one lands", () => {
    store().startRun("run_x");
    announce("attacker_doctrinal", "attacker_evidentiary");
    store().addTurn(turns[1]); // doctrinal reports

    // The judge is a fan-in. Previously the store had to work out for itself
    // that one attacker reporting must not start it; now it simply waits to
    // be told, and evidentiary stays pending in the meantime.
    expect(store().pendingRoles).toEqual(["attacker_evidentiary"]);
  });

  it("ignores a repeated announcement", () => {
    store().startRun("run_x");
    announce("judge", "judge");

    // A reconnect can repeat an event, and the round boundary announces the
    // presenter again. Two entries would show one bench waiting twice.
    expect(store().pendingRoles).toEqual(["judge"]);
  });

  it("clears the presenter when the presenter's turn arrives", () => {
    store().startRun("run_x");
    announce("presenter");
    store().addTurn(turns[0]);

    expect(store().pendingRoles).toEqual([]);
    expect(store().pendingSince).toBeNull();
  });

  it("clears the clerk when anyone else speaks", () => {
    store().startRun("run_x");
    announce("retriever");
    store().addTurn(turns[0]); // presenter

    // Retrieval emits no turn of its own, so nothing else can clear it.
    expect(store().pendingRoles).toEqual([]);
  });

  it("clears the wait when the judge rules", () => {
    store().startRun("run_x");
    announce("judge");
    for (const turn of turns) store().addTurn(turn);
    store().setVerdict(verdict);

    expect(store().pendingRoles).toEqual([]);
    expect(store().pendingSince).toBeNull();
  });

  it("clears the wait on error, so nothing spins forever", () => {
    store().startRun("run_x");
    announce("attacker_doctrinal");
    expect(store().pendingRoles).not.toEqual([]);

    store().setError("judge model unreachable");
    expect(store().pendingRoles).toEqual([]);
    expect(store().pendingSince).toBeNull();
  });

  it("measures one wait, not one per role", () => {
    store().startRun("run_x");
    announce("attacker_doctrinal");
    const since = store().pendingSince;

    // The second attacker joins a wait already under way. Restarting the
    // clock here would reset the visible timer mid-wait, which is the one
    // thing that distinguishes a slow model from a hung one.
    announce("attacker_evidentiary");
    expect(store().pendingSince).toBe(since);

    // Doctrinal lands but evidentiary is still out: same wait, same clock.
    store().addTurn(turns[1]);
    expect(store().pendingSince).toBe(since);
  });

  it("keeps going when the judge rules but the debate continues", () => {
    store().startRun("run_x");
    for (const turn of turns) store().addTurn(turn);

    // The judge rules every round, and the server re-emits the standing
    // verdict on each stream chunk. Treating the first one as the end of the
    // debate is what made a two-round run look frozen after round one.
    store().setVerdict(verdict);
    expect(store().phase).toBe("adjourned");

    announce("presenter");
    store().addTurn({ ...turns[0], id: "turn_presenter_r2", round_number: 2 });

    expect(store().phase).not.toBe("adjourned");
    expect(store().round).toBe(2);
  });

  it("ignores a verdict it has already seen", () => {
    store().startRun("run_x");
    for (const turn of turns) store().addTurn(turn);

    store().setVerdict(verdict);
    const firstSince = store().pendingSince;

    // The router emits the standing verdict again on the next chunk. It must
    // not restart anything or clobber a round already under way.
    store().setVerdict(verdict);
    expect(store().phase).toBe("adjourned");
    expect(store().pendingSince).toBe(firstSince);
  });

  it("holds a role announced in a later round, where everyone has spoken before", () => {
    store().startRun("run_x");
    for (const turn of turns) store().addTurn(turn);

    // The old inference had to scope "who is done" to the current round, or
    // in round two every role counted as finished and nothing was ever
    // pending. An announcement carries no such assumption.
    announce("attacker_doctrinal", "attacker_evidentiary");

    expect(store().pendingRoles).toEqual([
      "attacker_doctrinal",
      "attacker_evidentiary",
    ]);
  });
});

describe("the fixture announces roles the way the graph does", () => {
  it("announces both attackers before either reports", () => {
    const sequence = replayEvents
      .filter((e) => e.event === "role_started" || e.event === "turn")
      .map((e) =>
        e.event === "role_started"
          ? `start:${(e.data as { role: string }).role}`
          : `turn:${(e.data as Turn).role}`,
      );

    // The attackers fan out in parallel, so the live stream announces both
    // and only then delivers their turns. A fixture that interleaved them
    // would leave the fan-in path untested.
    const i = sequence.indexOf("start:attacker_doctrinal");
    expect(sequence.slice(i, i + 4)).toEqual([
      "start:attacker_doctrinal",
      "start:attacker_evidentiary",
      "turn:attacker_doctrinal",
      "turn:attacker_evidentiary",
    ]);
  });

  it("announces every role before its turn", () => {
    const announced = new Set<string>();
    for (const event of replayEvents) {
      if (event.event === "role_started") {
        announced.add((event.data as { role: string }).role);
      }
      if (event.event === "turn") {
        const role = (event.data as Turn).role;
        expect(announced.has(role), `${role} reported unannounced`).toBe(true);
        announced.delete(role);
      }
    }
  });
});
