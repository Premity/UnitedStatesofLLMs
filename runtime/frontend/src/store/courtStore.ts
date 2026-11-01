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

  turns: Turn[];
  verdict: Verdict | null;
  error: string | null;

  /** Which role's sprite is currently animating as speaking. */
  activeRole: Role | null;
  /** Objection currently shown with the slam flourish, if any. */
  flourish: Objection | null;
  /** Speech bubble text for the active role. */
  utterance: string | null;

  startRun: (runId: string, options?: { replayed?: boolean }) => void;
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
  round: 0,
  replayed: false,
  turns: [],
  verdict: null,
  error: null,
  activeRole: null,
  flourish: null,
  utterance: null,
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
      replayed: options?.replayed ?? false,
    }),

  setPhase: (phase) => set({ phase }),

  addTurn: (turn) =>
    set((state) => ({
      turns: [...state.turns, turn],
      round: Math.max(state.round, turn.round_number),
      activeRole: turn.role,
      phase: PHASE_FOR_ROLE[turn.role] ?? state.phase,
      // The bubble shows the headline of what the role just said: its first
      // claim, or its first objection.
      utterance:
        turn.arguments[0]?.claim ?? turn.objections[0]?.ground ?? null,
    })),

  setVerdict: (verdict) =>
    set({ verdict, phase: "adjourned", activeRole: "judge", utterance: verdict.conclusion }),

  setError: (error) => set({ error, phase: "error" }),

  showFlourish: (flourish) => set({ flourish }),

  reset: () => set(initial),
}));
