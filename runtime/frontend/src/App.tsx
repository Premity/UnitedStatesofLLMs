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

      {/* The record gives its column back when it is put away, so the
          courtroom widens instead of leaving a gap. */}
      <main
        className={`mx-auto grid max-w-[1600px] gap-6 p-6 ${
          dissentOpen
            ? "lg:grid-cols-[minmax(0,1fr)_minmax(0,28rem)]"
            : "lg:grid-cols-[minmax(0,1fr)_auto]"
        }`}
      >
        <div className="space-y-6">
          <QuestionForm />
          <Courtroom />
          <Transcript />
        </div>

        <DissentPanel />
      </main>
    </div>
  );
}
