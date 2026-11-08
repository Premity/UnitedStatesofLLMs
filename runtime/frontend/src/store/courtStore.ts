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
 * Who works next, given the role that just finished.
 *
 * Mirrors the graph in runtime/api/app/graph/workflow.py:
 *
 *   retrieve -> present -> [doctrinal || evidentiary] -> judge -> (loop or end)
 *
 * The attackers fan out together and the judge waits for both, so a wait can
 * belong to two roles at once. The judge is followed by nothing: either the
 * verdict arrives or another round begins with the presenter, and which it is
 * only becomes clear when the next event lands.
 *
 * Duplicated from the backend by necessity — the stream says nothing about
 * what is coming. If build_graph() changes, this has to change with it.
 */
const NEXT_ROLES: Record<string, Role[]> = {
  retriever: ["presenter"],
  presenter: ["attacker_doctrinal", "attacker_evidentiary"],
  attacker_doctrinal: ["judge"],
  attacker_evidentiary: ["judge"],
  judge: [],
};

/** Maps the role that just spoke to the phase the courtroom should show. */
const PHASE_FOR_ROLE: Record<string, CourtPhase> = {
  retriever: "retrieving",
  presenter: "presenting",
  attacker_doctrinal: "objecting",
  attacker_evidentiary: "objecting",
  judge: "ruling",
};

export const useCourtStore = create<CourtState>((set) => ({
  ...initial,

  startRun: (runId, options) =>
    set({
      ...initial,
      runId,
      phase: "retrieving",
      // Retrieval runs before anyone speaks, then the presenter opens.
      pendingRoles: ["retriever"] as Role[],
      pendingSince: Date.now(),
      replayed: options?.replayed ?? false,
      question: options?.question ?? null,
      facts: options?.facts ?? null,
    }),

  setPhase: (phase) => set({ phase }),

  addTurn: (turn) =>
    set((state) => {
      // This role is done. Whoever follows it is now working — unless they
      // have already reported, which happens when the slower attacker lands
      // after the faster one and both point at the judge.
      //
      // Scoped to this round: in round two every role has spoken before, so
      // judging against the whole run would leave nothing ever pending.
      const done = new Set(
        state.turns
          .filter((t) => t.round_number === turn.round_number)
          .map((t) => t.role),
      );
      done.add(turn.role);
      // Retrieval emits no turn of its own, so it can only be cleared by
      // someone else reporting — once anyone speaks, the clerk is finished.
      const stillPending = state.pendingRoles.filter(
        (r) => r !== turn.role && r !== "retriever" && !done.has(r),
      );
      // A role starts only when nothing it waits on is outstanding. The judge
      // is a fan-in: both attackers feed it, so the first one to report must
      // not start it while the other is still generating.
      const started = (NEXT_ROLES[turn.role] ?? []).filter(
        (r) =>
          !done.has(r) &&
          !stillPending.includes(r) &&
          !stillPending.some((p) => (NEXT_ROLES[p] ?? []).includes(r)),
      );
      const pendingRoles = [...stillPending, ...started];

      return {
        turns: [...state.turns, turn],
        round: Math.max(state.round, turn.round_number),
        activeRole: turn.role,
        phase: PHASE_FOR_ROLE[turn.role] ?? state.phase,
        pendingRoles,
        // Restart the clock only when this wait is a new one.
        pendingSince:
          pendingRoles.length === 0
            ? null
            : started.length > 0
              ? Date.now()
              : state.pendingSince,
        // The bubble shows the headline of what the role just said: its first
        // claim, or its first objection.
        utterance:
          turn.arguments[0]?.claim ?? turn.objections[0]?.ground ?? null,
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
