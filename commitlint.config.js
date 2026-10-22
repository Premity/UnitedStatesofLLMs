// Conventional Commits, enforced in CI and by the commit-msg hook.
//
//   feat(api): stream turn-level events over SSE
//   fix(indexer): preserve subparagraph locators when chunking Article 8
//   docs: document the corpus tiering rationale
//
// Scopes match the top-level areas of the repo so `git log --grep` is useful.

export default {
  extends: ["@commitlint/config-conventional"],
  rules: {
    "scope-enum": [
      2,
      "always",
      [
        "api",
        "core",
        "frontend",
        "fetcher",
        "indexer",
        "eval",
        "prompts",
        "corpus",
        "docker",
        "ci",
        "docs",
        "deps",
      ],
    ],
    // `lower-case` rejects proper nouns and class names that are correctly
    // capitalised -- "Groq", "RoleModels", "Mistral". Forbidding these styles
    // instead allows a capital *inside* the subject while still blocking
    // "Add a thing" and "Stream Turn Level Events".
    //
    // `sentence-case` fires on any capital first letter, so a subject that
    // opens with an acronym ("ADR 0008 ...") is still rejected. Reword it to
    // put the acronym later: "adr 0008 ..." or "record ADR 0008".
    "subject-case": [
      2,
      "never",
      ["sentence-case", "start-case", "pascal-case", "upper-case"],
    ],
    "header-max-length": [2, "always", 100],
    "body-max-line-length": [1, "always", 100],
  },
};
