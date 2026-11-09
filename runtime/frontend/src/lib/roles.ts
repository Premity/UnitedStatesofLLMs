import type { Role } from "@/types";

/**
 * How each role is named in the UI.
 *
 * Three forms, because the same role reads differently depending on where it
 * sits. `title` heads a transcript card; `sentence` goes inside running prose
 * ("waiting on doctrinal counsel"); `short` is the nameplate under a sprite,
 * where the bench is only seven characters wide.
 *
 * Collected here because the courtroom, the transcript, the band and the
 * replay narration all need them, and four copies drift.
 */

interface RoleNames {
  title: string;
  sentence: string;
  short: string;
}

const ROLE_NAMES: Record<string, RoleNames> = {
  retriever: { title: "Clerk", sentence: "the clerk", short: "Clerk" },
  presenter: {
    title: "Presenting Counsel",
    sentence: "presenting counsel",
    short: "Presenting Counsel",
  },
  attacker_doctrinal: {
    title: "Doctrinal Counsel",
    sentence: "doctrinal counsel",
    short: "Doctrinal",
  },
  attacker_evidentiary: {
    title: "Evidentiary Counsel",
    sentence: "evidentiary counsel",
    short: "Evidentiary",
  },
  judge: { title: "The Bench", sentence: "the bench", short: "The Bench" },
};

/** Falls back to the raw role id, so an unknown role is visible, not blank. */
export function roleTitle(role: Role | string): string {
  return ROLE_NAMES[role]?.title ?? role;
}

export function roleSentence(role: Role | string): string {
  return ROLE_NAMES[role]?.sentence ?? role;
}

export function roleShort(role: Role | string): string {
  return ROLE_NAMES[role]?.short ?? role;
}

/**
 * Whether a string from the wire is a role the courtroom can seat.
 *
 * The stream is a network boundary, and `Role` is a TypeScript type that does
 * not exist at runtime -- so a cast would make any string a `Role` and a new
 * graph node would reach the store as a bench that does not exist. Checked
 * against the display names, which is the set the UI can actually render.
 */
export function isRole(value: unknown): value is Role {
  return typeof value === "string" && value in ROLE_NAMES;
}
