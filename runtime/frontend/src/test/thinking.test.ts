import { describe, expect, it } from "vitest";

import { replayEvents } from "@/api/replay";
import { useCourtStore } from "@/store/courtStore";
import type { Turn, Verdict } from "@/types";

/**
 * Who the courtroom believes is working.
 *
 * The stream carries only completed turns, so this is inferred from the graph's
 * shape. These tests are the check on that inference: get it wrong and the
 * courtroom spends most of a debate pointing at the wrong bench.
 */

const turns = replayEvents
  .filter((e) => e.event === "turn")
  .map((e) => e.data as Turn);

const verdict = replayEvents.find((e) => e.event === "verdict")?.data as Verdict;

const store = () => useCourtStore.getState();

describe("inferring who is thinking", () => {
  it("waits on the clerk before anyone speaks", () => {
    store().startRun("run_x");

    expect(store().pendingRoles).toEqual(["retriever"]);
    expect(store().pendingSince).not.toBeNull();
  });

  it("hands off to the presenter, then to both attackers at once", () => {
    store().startRun("run_x");
    store().addTurn(turns[0]); // presenter

    // The attackers fan out together — the judge waits for both.
    expect(store().pendingRoles).toEqual([
      "attacker_doctrinal",
      "attacker_evidentiary",
    ]);
  });

  it("keeps the slower attacker pending when the faster one lands", () => {
    store().startRun("run_x");
    store().addTurn(turns[0]);
    store().addTurn(turns[1]); // doctrinal reports

    // Evidentiary is still working; the judge cannot start yet.
    expect(store().pendingRoles).toEqual(["attacker_evidentiary"]);
  });

  it("starts the judge only once both attackers have reported", () => {
    store().startRun("run_x");
    store().addTurn(turns[0]);
    store().addTurn(turns[1]);
    store().addTurn(turns[2]); // evidentiary reports

    expect(store().pendingRoles).toEqual(["judge"]);
  });

  it("clears the wait when the judge rules", () => {
    store().startRun("run_x");
    for (const turn of turns) store().addTurn(turn);
    store().setVerdict(verdict);

    expect(store().pendingRoles).toEqual([]);
    expect(store().pendingSince).toBeNull();
  });

  it("clears the wait on error, so nothing spins forever", () => {
    store().startRun("run_x");
    store().addTurn(turns[0]);
    expect(store().pendingRoles).not.toEqual([]);

    store().setError("judge model unreachable");
    expect(store().pendingRoles).toEqual([]);
    expect(store().pendingSince).toBeNull();
  });

  it("restarts the clock only when a new wait begins", () => {
    store().startRun("run_x");
    store().addTurn(turns[0]);
    const attackersSince = store().pendingSince;

    // Doctrinal lands but evidentiary is still out: the same wait continues,
    // so the clock must not reset.
    store().addTurn(turns[1]);
    expect(store().pendingSince).toBe(attackersSince);
  });

  it("works again in a later round, where every role has spoken before", () => {
    store().startRun("run_x");
    for (const turn of turns) store().addTurn(turn);

    // Round two opens with the presenter's rebuttal. Judged against the whole
    // run every role would count as finished and nothing would be pending.
    store().addTurn({ ...turns[0], id: "turn_presenter_r2", round_number: 2 });

    expect(store().pendingRoles).toEqual([
      "attacker_doctrinal",
      "attacker_evidentiary",
    ]);
    expect(store().round).toBe(2);
  });
});
