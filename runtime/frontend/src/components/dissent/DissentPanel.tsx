import { useEffect } from "react";

import { DissentLog } from "@/components/dissent/DissentLog";
import { useCourtStore } from "@/store/courtStore";
import { usePaneStore } from "@/store/paneStore";

/**
 * Holds the dissent log in a sidebar that can be put away.
 *
 * The record only exists once the court has ruled, so for most of a debate
 * the panel was 26rem of "the dissent log appears once the court has ruled"
 * beside the thing worth watching. Collapsed it is a rail; expanded it is the
 * document.
 *
 * It opens itself the first time a verdict lands — that is the moment the
 * record becomes worth reading — but never again after that, so reopening it
 * cannot fight someone who deliberately closed it.
 */
export function DissentPanel() {
  const { verdict, phase, runId } = useCourtStore();
  const { dissentOpen: open, setDissentOpen: setOpen, announceVerdict } =
    usePaneStore();

  useEffect(() => {
    if (verdict && runId) announceVerdict(runId);
  }, [announceVerdict, runId, verdict]);

  // A ruled-on debate has a record; before that the panel has nothing to show.
  const hasRecord = verdict !== null;

  if (!open) {
    return (
      <aside className="lg:sticky lg:top-6 lg:self-start">
        <button
          type="button"
          data-testid="dissent-open"
          onClick={() => setOpen(true)}
          aria-expanded={false}
          className="flex w-full items-center justify-between gap-3 rounded-xl border border-record-rule/50 bg-record-paper/10 px-4 py-3 text-left transition hover:bg-record-paper/20 lg:h-full lg:w-14 lg:flex-col lg:justify-start lg:px-0 lg:py-5"
        >
          <span className="font-display text-sm font-semibold text-court-gold lg:[writing-mode:vertical-rl]">
            Dissent Log
          </span>

          <span className="font-ui text-[11px] text-court-fg/40 lg:mt-3 lg:[writing-mode:vertical-rl]">
            {hasRecord
              ? `${verdict.dissent.length} overruled`
              : phase === "idle"
                ? "Not yet"
                : "Pending"}
          </span>
        </button>
      </aside>
    );
  }

  return (
    <div className="relative">
      <button
        type="button"
        data-testid="dissent-close"
        onClick={() => setOpen(false)}
        aria-expanded
        title="Put the record away"
        className="absolute right-3 top-3 z-10 rounded border border-record-rule bg-record-paper px-2 py-1 font-ui text-[11px] text-record-margin transition hover:bg-record-rule/40"
      >
        Close
      </button>

      <DissentLog />
    </div>
  );
}
