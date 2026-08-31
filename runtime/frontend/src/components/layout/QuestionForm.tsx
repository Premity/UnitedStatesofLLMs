import { useState } from "react";

import { useCourtStore } from "@/store/courtStore";
import { useDebateStream } from "@/hooks/useDebateStream";
import type { DebateConfig, Role } from "@/types";

/**
 * Puts a question to the council.
 *
 * The attacker toggles and round mode are exposed because they are exactly the
 * ablation dimensions the evaluation varies — being able to run a single-attacker
 * debate by hand makes the harness results legible.
 */
export function QuestionForm() {
  const { phase } = useCourtStore();
  const { start, stop } = useDebateStream();

  const [question, setQuestion] = useState("");
  const [facts, setFacts] = useState("");
  const [doctrinal, setDoctrinal] = useState(true);
  const [evidentiary, setEvidentiary] = useState(true);
  const [rounds, setRounds] = useState<"auto" | number>("auto");

  const running = phase !== "idle" && phase !== "adjourned" && phase !== "error";

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;

    const attackers: Role[] = [];
    if (doctrinal) attackers.push("attacker_doctrinal");
    if (evidentiary) attackers.push("attacker_evidentiary");

    const config: DebateConfig = {
      question: question.trim(),
      facts: facts.trim(),
      rounds,
      max_rounds: 3,
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
          className="mt-1 w-full rounded border border-court-rail bg-court-ink/60 p-3 font-record text-sm text-white/90 placeholder:text-white/25 focus:border-court-gold focus:outline-none disabled:opacity-50"
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
          className="mt-1 w-full rounded border border-court-rail bg-court-ink/60 p-3 font-record text-sm text-white/90 placeholder:text-white/25 focus:border-court-gold focus:outline-none disabled:opacity-50"
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
          <span className="font-ui text-xs text-white/60">Rounds</span>
          <select
            value={String(rounds)}
            onChange={(e) =>
              setRounds(e.target.value === "auto" ? "auto" : Number(e.target.value))
            }
            disabled={running}
            className="rounded border border-court-rail bg-court-ink/60 px-2 py-1 font-ui text-xs text-white/80 disabled:opacity-50"
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
          disabled={running || !question.trim()}
          className="rounded bg-court-gold px-5 py-2 font-display text-sm font-bold text-court-ink transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Convene the council
        </button>

        {running && (
          <button
            type="button"
            onClick={stop}
            className="rounded border border-court-crimson px-4 py-2 font-ui text-sm text-court-crimson transition hover:bg-court-crimson hover:text-white"
          >
            Adjourn
          </button>
        )}
      </div>
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
      <span className="font-ui text-xs text-white/60">{label}</span>
    </label>
  );
}
