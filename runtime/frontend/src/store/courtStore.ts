import { create } from "zustand";

import type { CourtPhase, Objection, Role, Turn, Verdict } from "@/types";

/**
 * Single source of truth for the courtroom.
 *
 * The store holds both the debate record (turns, objections, verdict) and the
 * presentational state the animation reads (who is speaking, whether an
 * OBJECTION! flourish is on screen). Keeping them together means one SSE event
 * updates both atomically and the sprites can never disagree with the record.
 */
interface CourtState {
  runId: string | null;
  phase: CourtPhase;
  round: number;

  /**
   * Whether this run came from a fixture rather than the models.
   *
   * Fabricated proceedings must never be mistakable for real ones, so the
   * provenance travels with the run itself rather than with the control that
   * started it — the courtroom and the record can both read it.
   */
  replayed: boolean;

  /**
   * What was put to the council.
   *
   * The Markdown export has carried these from the start; the screen did not,
   * so a holding could be read with no sight of the question it answers.
   */
  question: string | null;
  facts: string | null;

  turns: Turn[];
  verdict: Verdict | null;
  error: string | null;

  /** Which role's sprite is currently animating as speaking. */
  activeRole: Role | null;

  /**
   * Roles whose models are generating right now.
   *
   * Inferred, not reported. The stream carries only completed turns — there is
   * no "role started" event — so without this the courtroom spends 40 to 90
   * seconds at a time showing the role that has already *finished* lit up,
   * with nothing to say anyone is working. That is most of a debate.
   *
   * It is a set because both attackers run concurrently: they fan out from the
   * presenter and the judge waits for both.
   */
  pendingRoles: Role[];
  /** When the current wait began, for a progress read-out. */
  pendingSince: number | null;
  /** Objection currently shown with the slam flourish, if any. */
  flourish: Objection | null;
  /** Subtitle band text for the active role: its turn's headline. */
  utterance: string | null;

  startRun: (
    runId: string,
    options?: { replayed?: boolean; question?: string; facts?: string },
  ) => void;
  setPhase: (phase: CourtPhase) => void;
  roleStarted: (role: Role) => void;
  addTurn: (turn: Turn) => void;
  setVerdict: (verdict: Verdict) => void;
  setError: (error: string) => void;
  showFlourish: (objection: Objection | null) => void;
  reset: () => void;
}

const initial = {
  runId: null,
  phase: "idle" as CourtPhase,
  pendingRoles: [] as Role[],
  pendingSince: null as number | null,
  round: 0,
  replayed: false,
  question: null,
  facts: null,
  turns: [],
  verdict: null,
  error: null,
  activeRole: null,
  flourish: null,
  utterance: null,
};

/**
 * Which role is working comes from the server's `role_started` event, not from
 * a copy of the graph held here. This used to be a NEXT_ROLES table that
 * mirrored `build_graph()` and had to reproduce its fan-in by hand -- the
 * first attacker to report must not start the judge while the other is still
 * generating. Nothing kept that table in sync with the graph, so adding a
 * node silently showed the wrong bench thinking. The graph now reports its
 * own task starts (ISSUES.md, resolved).
 */

/** Maps the role that just spoke to the phase the courtroom should show. */
const PHASE_FOR_ROLE: Record<string, CourtPhase> = {
  retriever: "retrieving",
  presenter: "presenting",
  attacker_doctrinal: "objecting",
  attacker_evidentiary: "objecting",
  judge: "ruling",
};

/**
 * What a role saying nothing actually means.
 *
 * An empty turn is a designed outcome, not a failure: the attackers are
 * told not to manufacture an objection against a sound argument (see
 * `attacker_doctrinal_system.md`). An attacker that raises nothing is
 * conceding the point, which for a dissent log is a finding in itself --
 * an objection never raised cannot be overruled. Rendering that as silence
 * hid it.
 *
 * Counsel presenting and counsel attacking are doing different things, so
 * they decline differently.
 */
function nothingToSay(role: string): string {
  if (role === "presenter") return "Nothing further.";
  if (role.startsWith("attacker_")) return "No objection.";
  return "Nothing to add.";
}

export const useCourtStore = create<CourtState>((set) => ({
  ...initial,

  startRun: (runId, options) =>
    set({
      ...initial,
      runId,
      phase: "retrieving",
      // Left empty: the server announces `retriever` with a `role_started`
      // event of its own. Seeding it here as well would make the courtroom
      // claim the clerk is working before the graph says so -- and in replay,
      // where events come from a fixture, would show a role the fixture never
      // reported.
      pendingRoles: [] as Role[],
      pendingSince: null,
      replayed: options?.replayed ?? false,
      question: options?.question ?? null,
      facts: options?.facts ?? null,
    }),

  setPhase: (phase) => set({ phase }),

  /**
   * A role began working, as reported by the graph.
   *
   * Additive and idempotent: the server announces both attackers before
   * either finishes, and a reconnect can repeat an announcement. Clearing is
   * `addTurn`'s job -- a role stops being pending when its turn lands.
   */
  roleStarted: (role) =>
    set((state) => {
      if (state.pendingRoles.includes(role)) return state;
      return {
        pendingRoles: [...state.pendingRoles, role],
        phase: PHASE_FOR_ROLE[role] ?? state.phase,
        // The clock measures the wait that is running now. The first role of
        // a concurrent pair starts it; the second joins a wait already under
        // way, so restarting it would reset the visible timer mid-wait.
        pendingSince: state.pendingSince ?? Date.now(),
      };
    }),

  addTurn: (turn) =>
    set((state) => {
      // This role has reported, so it is no longer pending. Who works *next*
      // is not inferred here -- the server's `role_started` event says so.
      //
      // Retrieval emits no turn of its own, so it can only be cleared by
      // someone else reporting: once anyone speaks, the clerk is finished.
      const pendingRoles = state.pendingRoles.filter(
        (r) => r !== turn.role && r !== "retriever",
      );

      return {
        turns: [...state.turns, turn],
        round: Math.max(state.round, turn.round_number),
        activeRole: turn.role,
        phase: PHASE_FOR_ROLE[turn.role] ?? state.phase,
        pendingRoles,
        // Nothing outstanding stops the clock. Otherwise the wait that is
        // still running keeps the time it started with, so a concurrent
        // attacker landing does not reset the other's timer.
        pendingSince: pendingRoles.length === 0 ? null : state.pendingSince,
        // The headline of what the role just said: its first claim, or its
        // first objection -- or, when it said neither, that it had nothing
        // to say. Resolved here rather than in the band because this is the
        // only place that knows a turn arrived at all: `null` from a turn
        // with no content and `null` from a turn that has not come yet are
        // the same value, and they do not mean the same thing.
        utterance:
          turn.arguments[0]?.claim ??
          turn.objections[0]?.ground ??
          nothingToSay(turn.role),
      };
    }),

  setVerdict: (verdict) =>
    set({
      verdict,
      phase: "adjourned",
      activeRole: "judge",
      utterance: verdict.conclusion,
      // The court has ruled; nothing is still generating.
      pendingRoles: [],
      pendingSince: null,
    }),

  setError: (error) =>
    set({ error, phase: "error", pendingRoles: [], pendingSince: null }),

  showFlourish: (flourish) => set({ flourish }),

  reset: () => set(initial),
}));
