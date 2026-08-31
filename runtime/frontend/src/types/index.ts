// Mirrors the Pydantic models in packages/council-core. Keep in sync — the API
// contract is documented in docs/api-contract.md.

export type Role =
  | "presenter"
  | "attacker_doctrinal"
  | "attacker_evidentiary"
  | "judge"
  | "retriever";

export type CitationType = "treaty" | "case" | "customary" | "resolution";

export type CitationStatus =
  | "resolved"
  | "unresolved"
  | "out_of_corpus"
  | "misquoted";

export type ObjectionDisposition =
  | "sustained"
  | "overruled"
  | "partial"
  | "unaddressed";

export interface Citation {
  type: CitationType;
  instrument: string;
  article?: string | null;
  case_id?: string | null;
  paragraph?: string | null;
  rule_number?: number | null;
  quoted_text?: string | null;
}

export interface ResolvedCitation {
  citation: Citation;
  status: CitationStatus;
  corpus_text?: string | null;
  source_url?: string | null;
  note?: string | null;
}

export interface Argument {
  id: string;
  claim: string;
  reasoning: string;
  citations: Citation[];
  resolved_citations: ResolvedCitation[];
}

export interface Objection {
  id: string;
  raised_by: Role;
  target_argument_id: string;
  ground: string;
  reasoning: string;
  citations: Citation[];
  resolved_citations: ResolvedCitation[];
  disposition: ObjectionDisposition;
  disposition_reasoning?: string | null;
}

export interface Turn {
  id: string;
  round_number: number;
  role: Role;
  model_id: string;
  prompt_id: string;
  prompt_hash: string;
  arguments: Argument[];
  objections: Objection[];
  raw_response: string;
  started_at: string;
  completed_at?: string | null;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  error?: string | null;
}

export interface Verdict {
  conclusion: string;
  reasoning: string;
  confidence: number;
  confidence_reasoning: string;
  surviving_argument_ids: string[];
  dissent: Objection[];
}

export interface DebateConfig {
  question: string;
  facts: string;
  rounds: number | "auto";
  max_rounds: number;
  enabled_attackers: Role[];
  retrieval_enabled: boolean;
  top_k: number;
}

export interface RunMetadata {
  run_id: string;
  status: "pending" | "running" | "completed" | "failed";
  started_at: string;
  completed_at?: string | null;
  role_models: Record<string, string>;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  duration_seconds?: number | null;
  error?: string | null;
}

/** Phase of the courtroom animation state machine. */
export type CourtPhase =
  | "idle"
  | "retrieving"
  | "presenting"
  | "objecting"
  | "ruling"
  | "adjourned"
  | "error";
