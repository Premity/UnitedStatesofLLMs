import { useEffect, useLayoutEffect, useRef, useState } from "react";

import { isReplayEnabled } from "@/api/replay";
import { useCourtStore } from "@/store/courtStore";
import { useDebateStream } from "@/hooks/useDebateStream";
import { useReplay } from "@/hooks/useReplay";
import type { DebateConfig, Role } from "@/types";

/**
 * Puts a question to the council.
 *
 * The attacker toggles and round mode are exposed because they are exactly the
 * ablation dimensions the evaluation varies — being able to run a single-attacker
 * debate by hand makes the harness results legible.
 *
 * Under `?replay=1` the form plays a fixture instead of calling the API, so the
 * courtroom can be worked on without four reachable models. Both hooks are
 * instantiated unconditionally — hook order cannot depend on a flag — and only
 * the chosen one is driven.
 *
 * It folds away once the council convenes, so the courtroom has the screen for
 * the length of the debate, and unfolds again when the court rises. The
 * stepper is deliberately left out of the fold: it drives the replay, so
 * hiding it during a debate would take away the control you steer with.
 */
export function QuestionForm() {
  const { phase } = useCourtStore();
  const live = useDebateStream();
  const replay = useReplay();

  const replaying = isReplayEnabled();
  const { start, stop } = replaying ? replay : live;

  // Replay is reachable from the page in dev, not only from a URL nobody can
  // guess. Gated on import.meta.env.DEV so it never ships in a built bundle.
  const offerReplay = import.meta.env.DEV && !replaying;

  const [question, setQuestion] = useState("");
  const [facts, setFacts] = useState("");
  const [doctrinal, setDoctrinal] = useState(true);
  const [evidentiary, setEvidentiary] = useState(true);
  const [rounds, setRounds] = useState<"auto" | number>("auto");

  const running = phase !== "idle" && phase !== "adjourned" && phase !== "error";

  /**
   * Folded away while the court sits.
   *
   * Tracks `running` rather than being driven by it, so the fold can also be
   * worked by hand: once a debate ends the form comes back, and before one
   * starts you can put it away yourself.
   */
  const [folded, setFolded] = useState(false);

  /**
   * Hold the courtroom still across the fold.
   *
   * Folding removes height above the courtroom, and the browser keeps its
   * scroll offset rather than what you were looking at -- so the page jumps
   * and the scene slides up the screen. Measure where the courtroom sits in
   * the viewport before the layout changes, then put the scroll back so it
   * has not moved.
   */
  const anchorRef = useRef<number | null>(null);
  useLayoutEffect(() => {
    const top = anchorRef.current;
    anchorRef.current = null;
    if (top === null) return;

    const scene = document.querySelector("[data-testid='chamber']");
    if (!scene) return;

    const delta = scene.getBoundingClientRect().top - top;
    if (delta) window.scrollBy({ top: delta, behavior: "instant" });
  }, [folded]);

  /** Remember where the courtroom is, for the fold that is about to happen. */
  const anchor = () => {
    const scene = document.querySelector("[data-testid='chamber']");
    anchorRef.current = scene ? scene.getBoundingClientRect().top : null;
  };

  /** Fold with the courtroom held still, whether by hand or on its own. */
  const fold = (next: boolean) => {
    anchor();
    setFolded(next);
  };

  // Away when the council convenes, back when the court rises.
  useEffect(() => {
    anchor();
    setFolded(running);
    // `anchor` is stable in effect: it only reads the DOM.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [running]);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();

    if (replaying) {
      void replay.start();
      return;
    }

    if (!question.trim()) return;

    const attackers: Role[] = [];
    if (doctrinal) attackers.push("attacker_doctrinal");
    if (evidentiary) attackers.push("attacker_evidentiary");

    const config: DebateConfig = {
      question: question.trim(),
      facts: facts.trim(),
      rounds,
      // Auto stops at the default 2 rounds, the configuration that was
      // evaluated; picking a number runs up to that many.
      max_rounds: rounds === "auto" ? 2 : rounds,
      enabled_attackers: attackers,
      retrieval_enabled: true,
      top_k: 8,
    };

    void start(config);
  };

  return (
    <form
      onSubmit={submit}
      className="rounded-xl border border-court-rail bg-court-panel/60 p-5"
    >
      {/* The fold's handle. Always present, so the form can always be got
          back, and carrying no question text -- the question is in the
          transcript, and repeating it here would just be another thing
          covering the courtroom. */}
      <div className="flex items-center justify-between gap-3">
        <span className="font-ui text-xs uppercase tracking-wider text-court-gold">
          {folded ? (running ? "The council is sitting" : "Put a question") : "Put a question"}
        </span>
        <button
          type="button"
          data-testid="question-fold"
          onClick={() => fold(!folded)}
          aria-expanded={!folded}
          className="rounded border border-court-rail px-3 py-1 font-ui text-xs text-court-fg/60 transition hover:border-court-gold/40 hover:text-court-fg/90"
        >
          {folded ? "Edit the question" : "Fold away"}
        </button>
      </div>

      {/* Unmounted when folded, not merely hidden by a class: `hidden` is a
          stylesheet's job, so the fold would depend on Tailwind being
          applied. The field state lives in this component and outlives the
          fold either way, so nothing typed is lost. */}
      {!folded && (
      <div className="mt-4">
      {replaying && (
        <p
          data-testid="replay-banner"
          className="mb-4 rounded border border-court-gold/40 bg-court-gold/10 px-3 py-2 font-ui text-xs text-court-gold"
        >
          Replay mode — playing a recorded fixture, not calling the models. The
          question below is ignored.
        </p>
      )}

      <label className="block">
        <span className="font-ui text-xs uppercase tracking-wider text-court-gold">
          Question
        </span>
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          rows={2}
          disabled={running}
          placeholder="Does the strike constitute a war crime under Article 8(2)(b)(iv) of the Rome Statute?"
          className="mt-1 w-full rounded border border-court-rail bg-court-ink/60 p-3 font-record text-sm text-court-fg/90 placeholder:text-court-fg/25 focus:border-court-gold focus:outline-none disabled:opacity-50"
        />
      </label>

      <label className="mt-3 block">
        <span className="font-ui text-xs uppercase tracking-wider text-court-gold">
          Facts as given
        </span>
        <textarea
          value={facts}
          onChange={(e) => setFacts(e.target.value)}
          rows={4}
          disabled={running}
          placeholder="The factual predicate the council must reason from…"
          className="mt-1 w-full rounded border border-court-rail bg-court-ink/60 p-3 font-record text-sm text-court-fg/90 placeholder:text-court-fg/25 focus:border-court-gold focus:outline-none disabled:opacity-50"
        />
      </label>

      <div className="mt-4 flex flex-wrap items-center gap-4">
        <Toggle
          label="Doctrinal counsel"
          checked={doctrinal}
          onChange={setDoctrinal}
          disabled={running}
        />
        <Toggle
          label="Evidentiary counsel"
          checked={evidentiary}
          onChange={setEvidentiary}
          disabled={running}
        />

        <label className="flex items-center gap-2">
          <span className="font-ui text-xs text-court-fg/60">Rounds</span>
          <select
            value={String(rounds)}
            onChange={(e) =>
              setRounds(e.target.value === "auto" ? "auto" : Number(e.target.value))
            }
            disabled={running}
            className="rounded border border-court-rail bg-court-ink/60 px-2 py-1 font-ui text-xs text-court-fg/80 disabled:opacity-50"
          >
            <option value="auto">Auto</option>
            <option value="1">1</option>
            <option value="2">2</option>
            <option value="3">3</option>
          </select>
        </label>
      </div>

      <div className="mt-4 flex gap-2">
        <button
          type="submit"
          disabled={running || (!replaying && !question.trim())}
          className="rounded bg-court-gold px-5 py-2 font-display text-sm font-bold text-court-on-gold transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {replaying ? "Play the recorded debate" : "Convene the council"}
        </button>

        {offerReplay && (
          <button
            type="button"
            data-testid="replay-offer"
            onClick={() => void replay.start()}
            disabled={running}
            title="Plays a recorded fixture end to end. No models are called."
            className="rounded border border-court-gold/50 px-4 py-2 font-ui text-sm text-court-gold/90 transition hover:bg-court-gold/10 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Play sample debate
          </button>
        )}

        {running && (
          <button
            type="button"
            onClick={stop}
            className="rounded border border-court-crimson px-4 py-2 font-ui text-sm text-court-crimson transition hover:bg-court-crimson hover:text-court-fg"
          >
            Adjourn
          </button>
        )}
      </div>

      </div>
      )}

      {/* Stepping. A debate plays in about nine seconds, which is too fast to
          read, and the states worth inspecting — the objection flourish, the
          citation chips — are the transient ones.

          Outside the fold: this is what drives the replay, so folding the
          form away must not take the controls with it. */}
      {offerReplay && (
        <div
          data-testid="replay-stepper"
          className="mt-3 flex flex-wrap items-center gap-2 border-t border-court-rail/40 pt-3"
        >
          <button
            type="button"
            data-testid="replay-step"
            onClick={replay.step}
            disabled={replay.finished}
            className="rounded border border-court-gold/50 bg-court-gold/10 px-4 py-1.5 font-ui text-sm text-court-gold transition hover:bg-court-gold/20 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {replay.progress.applied === 0 ? "Step through it" : "Next step"}
          </button>

          <button
            type="button"
            data-testid="replay-restart"
            onClick={replay.restart}
            disabled={replay.progress.applied === 0}
            className="rounded border border-court-rail px-3 py-1.5 font-ui text-xs text-court-fg/60 transition hover:bg-court-fg/5 disabled:cursor-not-allowed disabled:opacity-30"
          >
            Restart
          </button>

          <span className="font-ui text-xs text-court-fg/40">
            {replay.finished
              ? `Done · ${replay.progress.total} of ${replay.progress.total}`
              : replay.nextLabel
                ? `Next: ${replay.nextLabel}`
                : "Steps one event at a time"}
          </span>
        </div>
      )}

    </form>
  );
}

function Toggle({
  label,
  checked,
  onChange,
  disabled,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <label className="flex items-center gap-2">
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
        className="h-4 w-4 accent-court-gold"
      />
      <span className="font-ui text-xs text-court-fg/60">{label}</span>
    </label>
  );
}
