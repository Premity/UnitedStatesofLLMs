import { Courtroom } from "@/components/courtroom/Courtroom";
import { DissentLog } from "@/components/dissent/DissentLog";
import { QuestionForm } from "@/components/layout/QuestionForm";
import { Transcript } from "@/components/layout/Transcript";
import { useCourtStore } from "@/store/courtStore";

/**
 * Two registers, side by side: the courtroom on the left is the live proceeding,
 * the dissent log on the right is the record it produces.
 */
export default function App() {
  const error = useCourtStore((s) => s.error);

  return (
    <div className="min-h-screen bg-court-bg text-white">
      <header className="border-b border-court-rail/60 px-6 py-4">
        <h1 className="font-display text-xl font-bold tracking-tight text-court-gold">
          United States of LLMs
        </h1>
        <p className="font-ui text-xs text-white/40">
          Adversarial review of international humanitarian law questions ·
          research prototype, not legal advice
        </p>
      </header>

      {error && (
        <div className="border-b border-court-crimson bg-court-crimson/15 px-6 py-3">
          <p className="font-ui text-sm text-court-crimson">{error}</p>
        </div>
      )}

      <main className="mx-auto grid max-w-[1600px] gap-6 p-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,26rem)]">
        <div className="space-y-6">
          <QuestionForm />
          <Courtroom />
          <Transcript />
        </div>

        <DissentLog />
      </main>
    </div>
  );
}
