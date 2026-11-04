import { create } from "zustand";

/**
 * Whether the record is open.
 *
 * Kept out of `courtStore` deliberately: that store is the debate, and
 * `reset()` clears it at the start of every run. Someone reading the record
 * from a finished debate should not have it close because a new one began —
 * this is a view preference, not part of the proceeding.
 *
 * The layout reads it too, so the grid can give the space back when the panel
 * is a rail rather than a document.
 */
interface PaneState {
  dissentOpen: boolean;
  /** The run whose verdict already opened the panel, so it opens once only. */
  announcedRun: string | null;

  setDissentOpen: (open: boolean) => void;
  /** Opens the record for a newly ruled run, unless it already did for it. */
  announceVerdict: (runId: string) => void;
}

export const usePaneStore = create<PaneState>((set, get) => ({
  dissentOpen: false,
  announcedRun: null,

  setDissentOpen: (dissentOpen) => set({ dissentOpen }),

  announceVerdict: (runId) => {
    if (get().announcedRun === runId) return;
    set({ announcedRun: runId, dissentOpen: true });
  },
}));
