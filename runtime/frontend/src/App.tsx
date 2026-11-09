import { Courtroom } from "@/components/courtroom/Courtroom";
import { DissentPanel } from "@/components/dissent/DissentPanel";
import { QuestionForm } from "@/components/layout/QuestionForm";
import { ThemeSwitcher } from "@/components/layout/ThemeSwitcher";
import { Transcript } from "@/components/layout/Transcript";
import { useCourtStore } from "@/store/courtStore";
import { usePaneStore } from "@/store/paneStore";

/**
 * Two registers, side by side: the courtroom on the left is the live proceeding,
 * the dissent log on the right is the record it produces.
 */
export default function App() {
  const error = useCourtStore((s) => s.error);
  const dissentOpen = usePaneStore((s) => s.dissentOpen);

  return (
    <div className="min-h-screen bg-court-bg text-court-fg">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-court-rail/60 px-6 py-4">
        <div>
          <h1 className="font-display text-xl font-bold tracking-tight text-court-gold">
            United States of LLMs
          </h1>
          <p className="font-ui text-xs text-court-fg/40">
            Adversarial review of international humanitarian law questions ·
            research prototype, not legal advice
          </p>
        </div>

        <ThemeSwitcher />
      </header>

      {error && (
        <div className="border-b border-court-crimson bg-court-crimson/15 px-6 py-3">
          <p className="font-ui text-sm text-court-crimson">{error}</p>
        </div>
      )}

      {/* The courtroom spans the page; the record splits the row beneath it.

          The dissent log used to be a column beside this whole stack, which
          meant opening it narrowed the courtroom. The room is drawn with
          `preserveAspectRatio="none"` over a box of fixed height, so
          narrowing it re-stretches the room horizontally while its height
          stays put, and every piece of furniture shifts relative to the
          figures standing at it. The scene's geometry must not depend on
          whether a panel elsewhere is open, so the split happens below it. */}
      <main className="mx-auto max-w-[1600px] space-y-6 p-6">
        <QuestionForm />
        <Courtroom />

        {/* The record gives its column back when it is put away, so the
            transcript widens instead of leaving a gap. Below `lg` it stacks
            under the transcript rather than squeezing it further. */}
        <div
          className={`grid gap-6 ${
            dissentOpen
              ? "lg:grid-cols-[minmax(0,1fr)_minmax(0,28rem)]"
              : "lg:grid-cols-[minmax(0,1fr)_auto]"
          }`}
        >
          <Transcript />
          <DissentPanel />
        </div>
      </main>
    </div>
  );
}
