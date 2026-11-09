import { useEffect, useState } from "react";

import { bandFor } from "@/components/dissent/Confidence";
import { roleShort } from "@/lib/roles";
import { useCourtStore } from "@/store/courtStore";
import type { Role } from "@/types";

import { Chamber, GalleryRail, JudgeBench, PresenterStand } from "./Chamber";
import { Sprite } from "./Sprite";
import { SubtitleBand } from "./SubtitleBand";

/**
 * The live view: four benches, a gallery, and whatever is happening right now.
 *
 * Layout mirrors an adversarial proceeding — the judge elevated at the back,
 * presenting counsel centred below, and the two challengers flanking. The
 * presenter at centre is the geometry of the thing: it is the role being
 * attacked from both sides. Doctrinal sits left and evidentiary right, fixed,
 * so a sprite does not move between runs.
 *
 * The sprite whose model is currently generating bobs; everyone else dims out.
 * What is being said goes in the band underneath, not in a bubble over the
 * scene.
 */

const PHASE_CAPTION: Record<string, string> = {
  idle: "The court is not in session.",
  retrieving: "Consulting the authorities…",
  presenting: "Counsel is presenting.",
  objecting: "Opposing counsel objects.",
  ruling: "The court is deliberating.",
  adjourned: "The court has ruled.",
  error: "Proceedings interrupted.",
};

const ROLE_WAITING: Record<string, string> = {
  retriever: "the clerk is consulting the corpus",
  presenter: "presenting counsel is preparing",
  attacker_doctrinal: "doctrinal counsel is reviewing",
  attacker_evidentiary: "evidentiary counsel is reviewing",
  judge: "the court is deliberating",
};

/**
 * How long the current wait has run.
 *
 * Elapsed, never estimated: a turn takes anywhere from 40 to 90 seconds and
 * nothing reports progress, so a countdown would be invented. Seeing the
 * seconds climb is what distinguishes a slow model from a hung one.
 */
function Elapsed({ since }: { since: number }) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    setNow(Date.now());
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [since]);

  const seconds = Math.max(0, Math.floor((now - since) / 1000));
  return (
    <>
      {seconds < 60
        ? `${seconds}s`
        : `${Math.floor(seconds / 60)}m ${seconds % 60}s`}
    </>
  );
}

export function Courtroom() {
  const {
    phase,
    round,
    activeRole,
    utterance,
    flourish,
    verdict,
    turns,
    replayed,
    pendingRoles,
    pendingSince,
  } = useCourtStore();

  const isThinking = (role: string) => pendingRoles.includes(role as Role);

  // Both attackers run concurrently, so name the pair rather than one of them.
  const waitingOn =
    pendingRoles.length === 2 &&
    pendingRoles.every((r) => r.startsWith("attacker_"))
      ? "opposing counsel are reviewing"
      : pendingRoles.length > 0
        ? ROLE_WAITING[pendingRoles[0]]
        : null;

  // The flourish belongs to the sprite that raised it. Anything other than
  // the two attackers is ignored rather than falling through to a default
  // bench: a judge cannot object, and a burst over the wrong figure would be
  // a lie about who said what.
  const objectionFor = (role: string) =>
    flourish?.raised_by === role ? flourish : null;

  // Model ids come off the most recent turn each role took.
  const modelFor = (role: string) =>
    [...turns].reverse().find((t) => t.role === role)?.model_id;

  return (
    <div className="flex flex-col gap-4">
      <section className="relative overflow-hidden rounded-xl border border-court-rail bg-gradient-to-b from-court-bg to-court-ink p-6 pb-10 shadow-2xl">
        <Chamber />
        {/* The bench is drawn in the room's coordinates but painted over the
            judge, so it sits here rather than inside the sprite: it spans
            the frame, and a sprite-scoped overlay cannot. */}
        <JudgeBench />
        {/* Likewise the lectern: drawn on the room's centre line, under the
            presenter rather than over them. */}
        <PresenterStand />
        {/* The rail crosses in front of counsel, so the gallery reads as
            behind them. Last of the furniture, and the frontmost. */}
        <GalleryRail />

        {/* Judge, elevated. The bench crosses the figure at y=54..112 of the
            room's 240, so the judge's height here decides how much of him
            rises above it. */}
        <div className="relative z-10 flex justify-center pb-2">
          <Sprite
            role="judge"
            label={roleShort("judge")}
            variant="judge"
            modelId={modelFor("judge")}
            speaking={activeRole === "judge"}
            thinking={isThinking("judge")}
            side="right"
          />
        </div>

        {/* Counsel: doctrinal left, presenter centre, evidentiary right.

            Three equal columns rather than a flex row so the presenter stays on
            the courtroom's axis under the bench whatever the nameplates are
            doing — a model id is as wide as it happens to be, and a flex row
            would let the longest one push the centre off. */}
        <div className="relative z-10 grid grid-cols-3 items-end gap-4 pt-6 sm:gap-8">
          <div className="flex justify-center sm:justify-end">
            <Sprite
              role="attacker_doctrinal"
              label={roleShort("attacker_doctrinal")}
              modelId={modelFor("attacker_doctrinal")}
              speaking={activeRole === "attacker_doctrinal"}
              thinking={isThinking("attacker_doctrinal")}
              objection={objectionFor("attacker_doctrinal")}
              side="left"
            />
          </div>

          {/* The presenter stands forward of the two attackers, nearer the
              viewer, and at the stand: offset down so the three do not sit
              on one flat line, which read as a row of cutouts rather than a
              room with depth. */}
          <div className="flex justify-center pt-12">
            <Sprite
              role="presenter"
              label={roleShort("presenter")}
              modelId={modelFor("presenter")}
              speaking={activeRole === "presenter"}
              thinking={isThinking("presenter")}
              side="right"
            />
          </div>

          <div className="flex justify-center sm:justify-start">
            <Sprite
              role="attacker_evidentiary"
              label={roleShort("attacker_evidentiary")}
              modelId={modelFor("attacker_evidentiary")}
              speaking={activeRole === "attacker_evidentiary"}
              thinking={isThinking("attacker_evidentiary")}
              objection={objectionFor("attacker_evidentiary")}
              side="right"
            />
          </div>
        </div>

        {/* Round and clock, pinned to the frame's top corner.

            Out of the rail and into the corner because they answer "where
            are we", not "what is happening": a glance target that should
            not share a line with the caption and compete with it. */}
        <div className="pointer-events-none absolute right-4 top-3 z-10 font-ui text-xs text-court-fg/40">
          {pendingSince !== null && (
            <span data-testid="elapsed" className="mr-2 tabular-nums">
              <Elapsed since={pendingSince} />
            </span>
          )}
          {round > 0 && `Round ${round}`}
          {verdict && (
            <>
              {" · "}
              <span title={bandFor(verdict.confidence).gloss}>
                {bandFor(verdict.confidence).label}
              </span>
            </>
          )}
        </div>

        {/* The caption, centred under the scene. It names whoever the court
            is waiting on, which is the one thing worth reading mid-debate,
            so it sits on the courtroom's axis rather than off to one side. */}
        <div className="relative z-10 mt-6 flex items-center justify-center gap-2 border-t border-court-rail/60 pt-3">
          <span className="flex items-center gap-2 font-ui text-xs uppercase tracking-widest text-court-gold/80">
            {/* Who is actually working beats a generic phase caption: a debate
                spends most of its time waiting, and "presenting" while the
                attackers generate names the wrong bench. */}
            {waitingOn ?? PHASE_CAPTION[phase] ?? phase}
            {replayed && (
              <span
                data-testid="replay-marker"
                title="A recorded fixture. No models were called."
                className="rounded border border-court-gold/40 px-1.5 py-0.5 text-[10px] tracking-wider text-court-gold/70"
              >
                Recorded
              </span>
            )}
          </span>
        </div>
      </section>

      {/* What is being said. Outside the courtroom frame, not floating over
          it: inside the section the drawn chamber ran behind the band, so the
          gallery rail disappeared underneath it. A separate block below the
          frame leaves the room whole and gives the band its own ground. */}
      <SubtitleBand role={activeRole} text={utterance} objection={flourish} />
    </div>
  );
}
